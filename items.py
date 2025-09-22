from types import UnionType
from typing import (
    Any,
    NotRequired,
    TypedDict,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
)


class Builder:
    def __init__(self, cls: type):
        self._cls = cls
        self._state: dict[str, Any] = {}

    def _check_cls_key(self, name):
        if name not in get_type_hints(self._cls):
            raise KeyError(f"key {name} is not defined for class {self._cls.__name__}")

    def _get_key_type(self, name):
        self._check_cls_key(name)
        hint = get_type_hints(self._cls)[name]
        origin = get_origin(hint)

        if not origin:
            return None, (hint,)
        # TODO: recursive origin check
        if origin is UnionType:
            return None, get_args(hint)
        if origin in (list, set):
            return origin, get_args(hint)
        raise TypeError(f"unknown type hint: {hint}")

    def put(self, key: str, value: Any):
        def check_value_type(value, allowed_types):
            # TODO: typeddict checks
            if (value_type := type(value)) not in set(
                t if not is_typeddict(t) else dict for t in allowed_types
            ):
                raise ValueError(
                    f"wrong type of the value supplied. expected: {allowed_types}, got: {value_type}"
                )

        # TODO: NoneType union check?
        # TODO: consider "not int, bool, etc."
        if not value and type(value) in (dict, list, set, str, tuple):
            return

        origin, args = self._get_key_type(key)
        if origin is list:
            if key not in self._state:
                self._state[key] = []
            check_value_type(value, args)
            self._state[key].append(value)
            return

        if origin is set:
            if key not in self._state:
                self._state[key] = set()
            check_value_type(value, args)
            self._state[key].add(value)
            return

        if key in self._state:
            raise AttributeError("attribute overwriting is not allowed")
        check_value_type(value, args)
        self._state[key] = value

    def build(self):
        hints = get_type_hints(self._cls)
        for key in hints:
            if key in self._cls.__required_keys__ and key not in self._state:
                raise ValueError(
                    f"missing {key} in {self._cls.__name__} Builder, cannot build the object"
                )
        return self._cls(**self._state)


class Recording(TypedDict):
    url: NotRequired[str]
    lang: str


class RecordingsAndTranscriptions(TypedDict):
    recordings: NotRequired[list[Recording]]
    transcriptions: NotRequired[list[str]]


class Term(TypedDict):
    value: str
    recordings_and_transcriptions: NotRequired[RecordingsAndTranscriptions]


class Ref(TypedDict):
    type: str
    terms: list[Term]


class ExampleSentence(TypedDict):
    sentence: str
    translation: str
    recordings_and_transcriptions: NotRequired[RecordingsAndTranscriptions]


class AdditionalInformation(TypedDict):
    language_register: NotRequired[list[str]]
    language_variety: NotRequired[str]
    other: NotRequired[str]
    popularity: NotRequired[int]


class Meaning(TypedDict):
    id: str
    terms: list[str]
    not_for_children: bool
    additional_information: NotRequired[AdditionalInformation]
    grammar_tags: NotRequired[list[str]]
    mf: NotRequired[str]
    example_sentences: NotRequired[list[ExampleSentence]]
    thematic_dictionaries: NotRequired[list[str]]
    note: NotRequired[str]
    refs: NotRequired[list[Ref]]
    copyright: NotRequired[str]


class Form(TypedDict):
    term: str
    type: str
    recordings_and_transcriptions: NotRequired[RecordingsAndTranscriptions]


class Header(TypedDict):
    title: str
    less_popular: bool
    additional_information: NotRequired[AdditionalInformation]
    recordings_and_transcriptions: NotRequired[RecordingsAndTranscriptions]


class MeaningGroup(TypedDict):
    meanings: list[Meaning]
    irregular_forms: NotRequired[list[Form]]
    part_of_speech: NotRequired[str]


class DictionaryEntity(TypedDict):
    headers: list[Header]
    meaning_groups: list[MeaningGroup]
    note: NotRequired[str]
    pictures: NotRequired[list[str]]
