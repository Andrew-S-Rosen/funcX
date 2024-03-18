import typing as t
from dataclasses import Field, asdict, dataclass, fields, is_dataclass

import typeguard


class ValidationError(Exception):
    pass


class DataClassValidator:
    def __init__(self, obj: t.Any) -> None:
        if not is_dataclass(obj):
            raise ValueError(f"{obj} must be a dataclass instance")
        self.obj = obj
        self.errors: dict[str, tuple[str]] = {}

    def _record_error(self, name: str, error: str):
        if name not in self.errors:
            self.errors[name] = ()
        self.errors[name] += (error,)

    def _validate_type(self, field: Field, val: t.Any):
        try:
            typeguard.check_type(val, field.type)
        except TypeError:
            self._record_error(field.name, f"Expected a value of type {field.type}")

    def _run_field_validator(self, field: Field, val: t.Any):
        field_validator = getattr(self.obj, f"validate_{field.name}", None)
        if field_validator is None:
            return
        try:
            validated_val = field_validator(val)
        except ValueError as e:
            self._record_error(field.name, (str(e)))
        else:
            setattr(self.obj, field.name, validated_val)

    def _run_object_validator(self):
        class_validator = getattr(self.obj, "validator", None)
        if class_validator is None:
            return
        data = asdict(self.obj)
        try:
            validated_data = class_validator(data)
        except ValueError as e:
            self._record_error(self.obj.__class__.__name__, (str(e)))
        else:
            for field, val in validated_data.items():
                setattr(self.obj, field, val)

    def validate(self):
        self.errors = {}

        for field in fields(self.obj):
            if field.name not in self.errors:
                self.errors[field.name] = []
            val = getattr(self.obj, field.name)
            self._validate_type(field, val)
            self._run_field_validator(field, val)
        self._run_object_validator()

        if self.errors:
            full_err_msg = ""
            for field, errors in self.errors.items():
                err_msg = f"\n{field}"
                for error in errors:
                    err_msg += f"\n  - {error}"
                full_err_msg += err_msg
            raise ValidationError(full_err_msg)


def validated_dataclass(cls):
    original_post_init = getattr(cls, "__post_init__", None)

    def __post_init__(self, *args, **kwargs):
        if original_post_init:
            original_post_init(self, *args, **kwargs)
        validator = DataClassValidator(self)
        validator.validate()

    cls.__post_init__ = __post_init__

    cls = dataclass(cls)
    return cls
