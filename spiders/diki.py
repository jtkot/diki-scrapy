import scrapy
import json


def get_text_content(selector: scrapy.Selector, recursive=True):
    return "".join(selector.xpath(".//text()" if recursive else "./text()").getall())


class DikiSpider(scrapy.Spider):
    name = "diki"

    async def start(self):
        urls = [
            "https://www.diki.pl/slownik-angielskiego?q=make",
        ]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    # RefItem {
    #     term: string; OK
    #     recordings_and_transcriptions?: RecordingsAndTranscriptions; OK
    # }

    # Ref {
    # 	_t_y_p_e_: string; OK
    #   items: RefItem[]; OK
    # }
    def parse_ref(self, ref_node: scrapy.Selector):
        ref = {"terms": [], "type": get_text_content(ref_node, False)}
        term = None
        for ref_child in ref_node.xpath("./div/*"):
            if "href" in ref_child.attrib:
                if term:
                    ref["terms"].append(term)
                term = {"value": get_text_content(ref_child)}
                continue
            for cls in ref_child.attrib["class"].split():
                match cls:
                    case "recordingsAndTranscriptions":
                        term["recordings_and_transcriptions"] = (
                            self.parse_recordings_and_transcriptions(ref_child)
                        )
                    case _:
                        print(
                            f"[WARNING]: unknown class {cls} found during: parse_refs"
                        )
        ref["terms"].append(term)
        return ref

    # Meaning {
    #     id: string; OK
    #     terms: string; OK
    #     not_for_children: boolean; TODO
    #     additional_information?: AdditionalInformation; OK
    #     grammar_tags?: string[]; OK
    #     mf?: string; OK // TODO: figure out what actually that is
    #     example_sentences?: ExampleSentence[]; OK
    #     thematic_dictionaries?: string[]; OK
    #     note?: string; OK
    #     refs?: Ref[] OK;
    #     copyright?: string OK;
    # }
    def parse_meaning(self, meaning_node: scrapy.Selector):
        meaning = {"id": meaning_node.attrib["id"][7:-3]}
        for meaning_child in meaning_node.xpath("./*"):
            for cls in meaning_child.attrib["class"].split():
                match cls:
                    case "hw":
                        meaning["terms"] = get_text_content(meaning_child).strip()
                    case "grammarTag":
                        meaning["grammar_tag"] = get_text_content(
                            meaning_child
                        ).strip()[1:-1]
                    case "meaningAdditionalInformation":
                        meaning["additional_information"] = (
                            self.parse_additional_information(meaning_child)
                        )
                    case "exampleSentence":
                        meaning.setdefault("example_sentences", []).append(
                            self.parse_example_sentence(meaning_child)
                        )
                    case "cat":
                        meaning.setdefault("thematic_dictionary", []).append(
                            get_text_content(meaning_child).strip()
                        )
                    case "ref":
                        meaning.setdefault("refs", []).append(
                            self.parse_ref(meaning_child)
                        )
                    case "nt":
                        meaning["note"] = get_text_content(meaning_child).strip()
                    case "mf":
                        meaning["mf"] = get_text_content(meaning_child).strip()
                    case "meaning_copyright":
                        meaning["copyright"] = get_text_content(meaning_child).strip()
                    case "repetitionAddOrRemoveIconAnchor":
                        pass
                    case _:
                        pass
        return meaning

    # Form {
    #     term: string; OK
    #     form: string; OK
    #     recordings_and_transcriptions?: RecordingsAndTranscriptions; OK
    # }
    def parse_forms(self, form_node: scrapy.Selector):
        forms = []
        form = None
        for form_child in form_node.xpath("./*"):
            for cls in form_child.attrib["class"].split():
                match cls:
                    case "foreignTermText":
                        if form:
                            forms.append(form)
                        form = {"term": get_text_content(form_child).strip()}
                    case "foreignTermHeader":
                        form["form"] = get_text_content(form_child).strip()
                    case "recordingsAndTranscriptions":
                        form["recordings_and_transcriptions"] = (
                            self.parse_recordings_and_transcriptions(form_child)
                        )
                    case _:
                        print(
                            f"[WARNING]: unknown class {cls} found during: parse_form"
                        )
        forms.append(form)
        return forms

    # ExampleSentence {
    #     sentence: string; OK
    #     translation: string; OK
    #     recordings_and_transcriptions?: RecordingsAndTranscriptions; OK
    # }
    def parse_example_sentence(self, es_node: scrapy.Selector):
        es = {"sentence": get_text_content(es_node, False).strip()}
        for es_child in es_node.xpath("./*"):
            for cls in es_child.attrib["class"].split():
                match cls:
                    case "exampleSentenceTranslation":
                        es["translation"] = get_text_content(es_child).strip()[1:-1]
                    case "recordingsAndTranscriptions":
                        es["recordings_and_transcriptions"] = (
                            self.parse_recordings_and_transcriptions(es_child)
                        )
                    case "repetitionAddOrRemoveIconAnchor":
                        continue
                    case _:
                        print(
                            f"[WARNING]: unknown class {cls} found during: parse_example_sequence"
                        )
        return es

    # Recording {
    # 	url: URL; OK
    #   lang: string OK
    # }

    # RecordingsAndTranscriptions {
    #     recordings?: Recording[]; OK
    #     transcriptions?: URL[]; OK
    # }
    def parse_recordings_and_transcriptions(self, rnt_node: scrapy.Selector):
        rnt = {}
        for rnt_child in rnt_node.xpath("./*"):
            for cls in rnt_child.attrib["class"].split():
                match cls:
                    case "hasRecording":
                        lang = rnt_child.attrib["class"].split()
                        lang.remove("hasRecording")
                        rnt.setdefault("recordings", []).append(
                            {
                                "url": rnt_child.css(":scope > .soundOnClick").attrib[
                                    "data-audio-url"
                                ],
                                "lang": lang[0],
                            }
                        )
                    case "phoneticTranscription":
                        rnt.setdefault("transcriptions", []).append(
                            rnt_child.css(":scope > a > img").attrib["src"]
                        )
                    case _:
                        print(
                            f"[WARNING]: unknown class {cls} found during: parse_recordings_and_transcriptions"
                        )
        return rnt

    # Header {
    #     title: string; OK
    #     less_popular: boolean; OK
    #     additional_information?: AdditionalInformation; OK
    #     recordings_and_transcriptions?: RecordingsAndTranscriptions; OK
    # }
    def parse_headers(self, header_node: scrapy.Selector):
        header = None
        headers = []
        for header_child in header_node.xpath("./*"):
            if header_child.get().strip() == "<br>":
                if header:
                    headers.append(header)
                    header = None
                    continue
            for cls in header_child.attrib["class"].split():
                match cls:
                    case "hw":
                        if header:
                            headers.append(header)
                        header = {"less_popular": False}
                        header["title"] = get_text_content(header_child).strip()
                    case "hwLessPopularAlternative":
                        header["less_popular"] = True
                    case "recordingsAndTranscriptions":
                        header["recordings_and_transcriptions"] = (
                            self.parse_recordings_and_transcriptions(header_child)
                        )
                    case "dictionaryEntryHeaderAdditionalInformation":
                        header["additional_information"] = (
                            self.parse_additional_information(header_child)
                        )
                    case "hwcomma":
                        break
                    case _:
                        print(
                            f"[WARNING]: unknown class {cls} found when building header"
                        )
        headers.append(header)
        return headers

    # AdditionalInformation {
    #     language_register?: string[]; OK
    #     language_variety?: string; OK
    #     other?: string[]; TODO
    #     popularity?: number; OK
    # }
    def parse_additional_information(self, ai_node: scrapy.Selector):
        ai = {}
        for ai_child in ai_node.xpath("./*"):
            for cls in ai_child.attrib["class"].split():
                match cls:
                    case "starsForNumOccurrences":
                        ai["popularity"] = len(get_text_content(ai_child).strip())
                    case "languageVariety":
                        ai["language_variety"] = get_text_content(ai_child).strip()
                    case "languageRegister":
                        ai.setdefault("language_register", []).append(
                            get_text_content(ai_child).strip()
                        )
                    case _:
                        print(
                            f'[WARNING]: unknown item class "{cls}" found when building additional_information'
                        )
        return ai

    # MeaningGroup {
    #     meanings: Meaning[]; OK
    #     irregular_forms?: Form[]; OK
    #     part_of_speech?: string; OK
    # }

    # DictionaryEntity {
    #     headers: Header[]; OK
    #     meaning_groups: MeaningGroup[]; OK
    #     note?: string; OK
    #     pictures?: URL[]; OK
    # }
    def parse_entity(self, entityEl: scrapy.Selector):
        entity = {"meaning_groups": []}
        meaning_group = None
        for child in entityEl.xpath("./*"):
            for cls in child.attrib["class"].split():
                match cls:
                    case "hws":
                        entity["header"] = self.parse_headers(child.css(":scope > h1"))
                        note = child.css(":scope > .nt").get()
                        if note:
                            entity["note"] = note
                    case "dictpict":
                        entity["pictures"] = child.css(":scope > img").attrib["src"]
                    case "partOfSpeechSectionHeader":
                        if meaning_group:
                            entity["meaning_groups"].append(meaning_group)
                        meaning_group = {}
                        meaning_group["part_of_speech"] = get_text_content(
                            child.css(":scope > .partOfSpeech")
                        ).strip()
                    case "foreignToNativeMeanings":
                        if not meaning_group:
                            meaning_group = {}
                        elif "meanings" in meaning_group:
                            entity["meaning_groups"].append(meaning_group)
                            meaning_group = {}
                        meaning_group["meanings"] = [
                            self.parse_meaning(meaning_node)
                            for meaning_node in child.css(":scope > li")
                        ]
                    case "vf":
                        meaning_group["irregular_forms"] = self.parse_forms(child)
                    case "additionalSentences":
                        continue
                    case _:
                        print(
                            f'[WARNING]: unknown item class "{cls}" found when building entity'
                        )
        entity["meaning_groups"].append(meaning_group)
        return entity

    def parse(self, response: scrapy.http.Response):
        for entity in response.xpath(
            '//*[@id="en-pl"]/../following-sibling::*[@class="diki-results-container"]/*[@class="diki-results-left-column"]/*/*[@class="dictionaryEntity"]'
        ):
            print(json.dumps(self.parse_entity(entity)))
