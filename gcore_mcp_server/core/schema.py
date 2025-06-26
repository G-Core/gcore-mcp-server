"""Type to JSON Schema conversion functionality."""

import inspect
from typing import (
    Any, Optional, Union, get_type_hints, Literal, Iterable,
    get_origin, get_args
)

try:
    # For TypedDict introspection and Required/NotRequired:
    # These are in `typing` from Python 3.9/3.11, or `typing_extensions` for older.
    from typing import is_typeddict, Required, NotRequired # type: ignore
except ImportError:
    from typing_extensions import is_typeddict, Required, NotRequired # type: ignore # noqa: F811

# For broader iterable check including runtime-origin from typing generics
from collections.abc import Sequence, Iterable as abcIterable, Set as abcSet, Collection

from gcore import NotGiven
from pydantic import BaseModel, ConfigDict
from ..domain import get_gcore_domain_handler


# Create a base model with arbitrary types allowed for SDK types
class SDKBaseModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


def convert_sdk_type(param_type: Any) -> Any:
    """
    Convert SDK specific types or wrappers like Union[X, NotGiven] to Optional[X].
    Also strips outer Required/NotRequired wrappers for some legacy compatibility if needed,
    though convert_param_type_to_schema_type should primarily handle this.
    """
    origin = get_origin(param_type)
    args = get_args(param_type)

    if origin is Union and NotGiven in args:
        # Handle Union[SomeType, NotGiven]
        actual_args = [arg for arg in args if arg is not NotGiven]
        if not actual_args:
            return Optional[Any]
        if len(actual_args) == 1:
            return Optional[actual_args[0]]
        # For Union[T1, T2, NotGiven] -> Optional[Union[T1, T2]]
        return Optional[Union[tuple(actual_args)]] # type: ignore

    # Strip Required/NotRequired if they are outermost for some reason here,
    # though primary handling is in convert_param_type_to_schema_type
    if origin is Required or origin is NotRequired:
        if args:
            return args[0] # Return the inner type
        return Any # Fallback

    return param_type


def convert_param_type_to_schema_type(param_type: Any, param_name: str = "") -> dict[str, Any]:
    """Convert Python type annotations to JSON Schema types.
    
    Args:
        param_type: Type annotation.
        param_name: Optional parameter name, for contextual schema generation.
        
    Returns:
        dict: JSON Schema type definition
    """
    origin = get_origin(param_type)
    args = get_args(param_type)

    # Handle Required[T] and NotRequired[T] by processing T
    if origin is Required or origin is NotRequired:
        if args:
            inner_schema = convert_param_type_to_schema_type(args[0], param_name)
            # The "required" status is usually handled by the parent (e.g., TypedDict required_keys list)
            # but we can add a note if it's a direct Required annotation.
            if origin is Required and "description" in inner_schema:
                inner_schema["description"] = (inner_schema.get("description", "") + " (explicitly required)").strip()
            elif origin is Required:
                inner_schema["description"] = "(explicitly required)"
            return inner_schema
        return {"type": "object", "description": "Any type (from empty Required/NotRequired)"}

    # Handle basic types
    if param_type is int:
        return {"type": "integer"}
    if param_type is float:
        return {"type": "number"}
    if param_type is bool:
        return {"type": "boolean"}
    if param_type is str:
        return {"type": "string"}
    if param_type is Any or param_type is inspect.Parameter.empty or param_type is inspect._empty: # type: ignore
        # For tools, Any usually means the LLM can provide a flexible structure, often an object.
        return {"type": "object", "description": "Any type, can be a flexible JSON object or an appropriate primitive."}
    if param_type is None or param_type is type(None):
        return {"type": "null"}

    # Handle Literal types
    if origin is Literal:
        enum_values = list(args)
        schema_type = "string"  # Default type for literals
        if enum_values:
            if isinstance(enum_values[0], bool):
                schema_type = "boolean"
            elif isinstance(enum_values[0], int):
                schema_type = "integer"
            elif isinstance(enum_values[0], float):
                schema_type = "number"
        
        enum_desc = f"Must be one of: {', '.join(map(repr, enum_values))}" # Use repr for string literals
        return {"type": schema_type, "enum": enum_values, "description": enum_desc}

    # Handle Union types (including Optional[T] which is Union[T, NoneType])
    if origin is Union:
        non_none_args = [arg for arg in args if arg is not type(None) and arg is not NotGiven]
        is_optional = type(None) in args or NotGiven in args

        if not non_none_args: 
            return {"type": "null"}
        
        if len(non_none_args) == 1:
            schema = convert_param_type_to_schema_type(non_none_args[0], param_name)
            if is_optional:
                if "description" in schema:
                    schema["description"] += " (optional)"
                else:
                    schema["description"] = "Optional"
            return schema
        
        one_of_schemas: list[dict[str,Any]] = [] # Ensure list is typed
        type_names_for_desc: list[str] = []

        for arg_type in non_none_args:
            current_param_name_for_recursion = getattr(arg_type, "__name__", param_name)
            schema = convert_param_type_to_schema_type(arg_type, current_param_name_for_recursion)
            one_of_schemas.append(schema)
            type_names_for_desc.append(getattr(arg_type, "__name__", str(arg_type)))
        
        if is_optional:
            one_of_schemas.append({"type": "null"})
        
        union_desc = f"One of the following types: {', '.join(type_names_for_desc)}"
        if is_optional:
            union_desc += " or null"

        final_schema: dict[str, Any] = {"oneOf": one_of_schemas, "description": union_desc}
        
        # Domain-specific enhancements using domain handler
        domain_handler = get_gcore_domain_handler()
        if domain_handler.is_special_parameter(param_name):
            enhanced_desc = domain_handler.get_union_type_description_enhancement(param_name, union_desc)
            final_schema["description"] = enhanced_desc

        return final_schema

    # Handle TypedDict
    if is_typeddict(param_type):
        type_name = getattr(param_type, "__name__", "TypedDict")
        properties: dict[str, dict[str,Any]] = {}
        required_keys_set: set[str] = set()
        
        field_hints = get_type_hints(param_type, include_extras=True)
        docstring = inspect.getdoc(param_type) or ""
        field_docstrings = _parse_typeddict_field_docstrings(docstring, list(field_hints.keys()))

        # Determine required keys
        if hasattr(param_type, '__required_keys__'):
            required_keys_set.update(param_type.__required_keys__)
        elif getattr(param_type, '__total__', True): 
            required_keys_set.update(k for k, v_type in field_hints.items() 
                                     if not (get_origin(v_type) is NotRequired or 
                                             (get_origin(v_type) is Union and type(None) in get_args(v_type))))
            for k, v_type in field_hints.items():
                if get_origin(v_type) is NotRequired and k in required_keys_set:
                    required_keys_set.remove(k)
        for k, v_type in field_hints.items():
            if get_origin(v_type) is Required:
                required_keys_set.add(k)
        
        for field_name, field_type_hint in field_hints.items():
            actual_field_type = field_type_hint
            if get_origin(field_type_hint) is Required or get_origin(field_type_hint) is NotRequired:
                actual_field_type = get_args(field_type_hint)[0] if get_args(field_type_hint) else Any
            
            field_schema = convert_param_type_to_schema_type(actual_field_type, field_name)
            
            if field_name in field_docstrings:
                field_schema["description"] = field_docstrings[field_name]
            elif "description" not in field_schema:
                field_schema["description"] = f"Field: {field_name}"
            
            properties[field_name] = field_schema
        
        schema: dict[str, Any] = {"type": "object", "properties": properties}
        if required_keys_set:
            schema["required"] = sorted(list(required_keys_set))
        
        main_doc = docstring.split("\n\n")[0].strip()
        if main_doc and not any(field_name + ":" in main_doc for field_name in field_hints.keys()):
            schema["description"] = f"Object of type {type_name}: {main_doc}"
        else:
            schema["description"] = f"Object of type {type_name}"
            
        return schema

    # Handle List, Iterable, Set, Sequence (from collections.abc)
    if origin in (list, set, tuple, Iterable, abcIterable, Sequence, abcSet, Collection):
        item_type = args[0] if args else Any
        item_param_name = f"{param_name}_item" if param_name else "item"
        items_schema = convert_param_type_to_schema_type(item_type, item_param_name)
        
        item_type_name = getattr(item_type, "__name__", str(item_type))
        array_description = f"Array of {item_type_name}"
        
        final_array_schema: dict[str, Any] = {
            "type": "array",
            "items": items_schema,
            "description": array_description
        }
        
        # Domain-specific enhancements using domain handler
        domain_handler = get_gcore_domain_handler()
        if domain_handler.is_special_parameter(param_name):
            domain_description = domain_handler.get_parameter_description(param_name, array_description)
            domain_examples = domain_handler.get_parameter_examples(param_name)
            
            final_array_schema["description"] = domain_description
            if domain_examples:
                final_array_schema["examples"] = domain_examples
            
        return final_array_schema
    
    # Handle dict types
    if origin is dict:
        value_type = args[1] if len(args) > 1 else Any
        value_schema = convert_param_type_to_schema_type(value_type, f"{param_name}_value" if param_name else "")
        
        return {
            "type": "object",
            "additionalProperties": value_schema,
            "description": f"Dictionary with string keys and values of type {getattr(value_type, '__name__', str(value_type))}"
        }
    
    # Handle Pydantic models (full JSON schema generation)
    if inspect.isclass(param_type) and issubclass(param_type, BaseModel):
        # Use Pydantic's own JSON schema generation for full detail when possible.
        try:
            json_schema = param_type.model_json_schema()
            # Ensure top-level type is object for models
            if "type" not in json_schema:
                json_schema["type"] = "object"
            # Attach first docstring line as description if not already present
            if "description" not in json_schema:
                raw_doc = inspect.getdoc(param_type)
                if raw_doc and not raw_doc.startswith("dict() ->"):
                    json_schema["description"] = raw_doc.split("\n\n")[0].strip()
                else:
                    json_schema["description"] = f"Pydantic model: {param_type.__name__}"
            return json_schema
        except Exception:
            # Fallback to simple description if schema generation fails
            type_name = param_type.__name__
            raw_doc = inspect.getdoc(param_type)
            if raw_doc and not raw_doc.startswith("dict() ->"):
                description = raw_doc.split("\n\n")[0].strip()
            else:
                description = f"Pydantic model: {type_name}"
            return {"type": "object", "description": description}

    # Handle other class types (generic object)
    if inspect.isclass(param_type):
        type_name = param_type.__name__
        raw_doc = inspect.getdoc(param_type) or ""

        # If the class defines __annotations__, treat it similar to a dataclass/TypedDict for schema purposes
        if hasattr(param_type, "__annotations__") and param_type.__annotations__:
            class_properties: dict[str, Any] = {}
            for attr_name, attr_type in param_type.__annotations__.items():
                class_properties[attr_name] = convert_param_type_to_schema_type(attr_type, attr_name)

            schema: dict[str, Any] = {
                "type": "object",
                "properties": class_properties,
            }

            if raw_doc and not raw_doc.startswith("dict() ->"):
                schema["description"] = raw_doc.split("\n\n")[0].strip()
            else:
                schema["description"] = f"Object of type {type_name}"

            return schema

        # Fallback simple description if no annotations available
        if raw_doc and not raw_doc.startswith("dict() ->"):
            description = raw_doc.split("\n\n")[0].strip()
        else:
            description = f"Object of type {type_name}"
        return {"type": "object", "description": description}

    # Fallback for unhandled types
    type_repr = str(param_type)
    if type_repr.startswith("<class '") and type_repr.endswith("'>"):
        type_repr = type_repr[8:-2]
    return {"type": "object", "description": f"Data of type {type_repr} (schema generation may be incomplete for this type)"}


def _parse_typeddict_field_docstrings(class_docstring: str, field_names: list[str]) -> dict[str, str]:
    """Helper to parse field docstrings from a TypedDict's main docstring."""
    field_docs: dict[str, str] = {}
    if not class_docstring:
        return field_docs

    lines = class_docstring.split('\n')
    current_field: Optional[str] = None
    current_doc_lines: list[str] = []

    for line in lines:
        stripped_line = line.strip()
        if not stripped_line: # End of a block
            if current_field and current_doc_lines:
                field_docs[current_field] = ' '.join(current_doc_lines).strip()
            current_field = None
            current_doc_lines = []
            continue

        found_new_field = False
        for field_name in field_names:
            # Common patterns: "field_name: description", "field_name (type): description"
            if stripped_line.startswith(f"{field_name}:") or stripped_line.startswith(f"{field_name} ("):
                if current_field and current_doc_lines: # Save previous field's doc
                    field_docs[current_field] = ' '.join(current_doc_lines).strip()
                
                current_field = field_name
                # Extract description part after the colon or type hint
                desc_part = ""
                if ":" in stripped_line:
                    desc_part = stripped_line.split(":", 1)[1].strip()
                current_doc_lines = [desc_part] if desc_part else []
                found_new_field = True
                break
        
        if found_new_field:
            continue

        if current_field: # If we are in a field's docstring block (multi-line)
            current_doc_lines.append(stripped_line)
    
    # Save the last field's docstring if any
    if current_field and current_doc_lines:
        field_docs[current_field] = ' '.join(current_doc_lines).strip()
        
    return field_docs 