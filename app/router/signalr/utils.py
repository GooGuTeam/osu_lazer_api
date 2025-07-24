import inspect
from typing import Any, Callable, ForwardRef, cast


# https://github.com/pydantic/pydantic/blob/main/pydantic/v1/typing.py#L56-L66
def evaluate_forwardref(
    type_: ForwardRef,
    globalns: Any,
    localns: Any,
) -> Any:
    # Even though it is the right signature for python 3.9,
    # mypy complains with
    # `error: Too many arguments for "_evaluate" of
    # "ForwardRef"` hence the cast...
    return cast(Any, type_)._evaluate(
        globalns,
        localns,
        set(),
    )


def get_annotation(param: inspect.Parameter, globalns: dict[str, Any]) -> Any:
    annotation = param.annotation
    if isinstance(annotation, str):
        annotation = ForwardRef(annotation)
        try:
            annotation = evaluate_forwardref(annotation, globalns, globalns)
        except Exception:
            return inspect.Parameter.empty
    return annotation


def get_signature(call: Callable[..., Any]) -> inspect.Signature:
    signature = inspect.signature(call)
    globalns = getattr(call, "__globals__", {})
    typed_params = [
        inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=get_annotation(param, globalns),
        )
        for param in signature.parameters.values()
    ]
    return inspect.Signature(typed_params)
