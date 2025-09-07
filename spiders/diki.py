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

    def parse_refs(self, ref_node: scrapy.Selector):
        ref = None
        refs = []
        for ref_child in ref_node.xpath('./div/*'):
                if 'href' in ref_child.attrib:
                    if ref:
                        refs.append(ref)
                    ref = {"term": get_text_content(ref_child)}
                    continue
                for cls in ref_child.attrib["class"].split():
                    match cls:
                        case "recordingsAndTranscriptions":
                            recordings, transcriptions = self.parse_recordings_and_transcriptions(ref_child)
                            ref.setdefault("recordings", []).extend(recordings)
                            ref.setdefault("transcriptions", []).extend(transcriptions)
                        case _:
                            print(f"[WARNING]: unknown class {cls} found during: parse_refs")
        refs.append(ref)
        return refs

    def parse_meaning(self, meaning_node: scrapy.Selector):
        meaning = {"id": meaning_node.attrib["id"][7:-3]}
        # TODO: uzwględnij nie dla dzieci
        for meaning_child in meaning_node.xpath("./*"):
            for cls in meaning_child.attrib["class"].split():
                match cls:
                    case "hw":
                        meaning['terms'] = get_text_content(meaning_child).strip()
                    case "grammarTag":
                        meaning['grammar_tag'] = get_text_content(meaning_child).strip()[1:-1]
                    case "meaningAdditionalInformation":
                        meaning['additional_information']  = (
                            self.parse_header_additional_information(meaning_child)
                        )
                    case "exampleSentence":
                        meaning.setdefault('example_sentence', []).append(self.parse_example_sentence(meaning_child))
                    case "cat":
                        meaning['thematic_dictionary'] = get_text_content(meaning_child).strip()
                    case "ref":
                        meaning['refs'] = self.parse_refs(meaning_child)
                    case "nt":
                        meaning['note'] = get_text_content(meaning_child).strip()
                    case "mf":
                        meaning['mf'] = get_text_content(meaning_child).strip()
                    case "meaning_copyright":
                        meaning['copyright'] = get_text_content(meaning_child).strip()
                    case "repetitionAddOrRemoveIconAnchor":
                        pass
                    case _:
                        pass
                    # terms = child.textContent?.trim()
        return meaning

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
                        recordings, transcriptions = self.parse_recordings_and_transcriptions(form_child)
                        form.setdefault("recordings", []).extend(recordings)
                        form.setdefault("transcriptions", []).extend(transcriptions)
                    case _:
                        print(
                            f"[WARNING]: unknown class {cls} found during: parse_form"
                        )
        forms.append(form)
        return forms

    def parse_example_sentence(self, es_node: scrapy.Selector):
        es = {"sentence": get_text_content(es_node, False).strip()}
        for es_child in es_node.xpath("./*"):
            for cls in es_child.attrib["class"].split():
                match cls:
                    case "exampleSentenceTranslation":
                        es["translation"] = get_text_content(es_child).strip()[1:-1]
                    case "recordingsAndTranscriptions":
                        recordings, transcriptions = self.parse_recordings_and_transcriptions(es_child)
                        es.setdefault("recordings", []).extend(recordings)
                        es.setdefault("transcriptions", []).extend(transcriptions)
                    case "repetitionAddOrRemoveIconAnchor":
                        continue
                    case _:
                        print(
                            f"[WARNING]: unknown class {cls} found during: parse_example_sequence"
                        )
        return es

    def parse_recordings_and_transcriptions(self, rnt_node: scrapy.Selector):
        rnt = ([], [])
        for rnt_child in rnt_node.xpath("./*"):
            for cls in rnt_child.attrib["class"].split():
                match cls:
                    case "hasRecording":
                        rnt[0].append(
                            rnt_child.css(":scope > .soundOnClick").attrib[
                                "data-audio-url"
                            ]
                        )
                    case "phoneticTranscription":
                        rnt[1].append(
                            rnt_child.css(":scope > a > img").attrib["src"]
                        )
                    case _:
                        print(
                            f"[WARNING]: unknown class {cls} found during: parse_recordings_and_transcriptions"
                        )
        return rnt

    def parse_header(self, header_node: scrapy.Selector):
        header_item = None
        header = []
        for header_child in header_node.xpath("./*"):
            if header_child.get().strip() == "<br>":
                if header_item:
                    header.append(header_item)
                    header_item = None
                    continue
            for cls in header_child.attrib["class"].split():
                match cls:
                    case "hw":
                        if header_item:
                            header.append(header_item)
                        header_item = {"less_popular": False}
                        header_item["title"] = get_text_content(header_child).strip()
                    case "hwLessPopularAlternative":
                        header_item["less_popular"] = True
                    case "recordingsAndTranscriptions":
                        recordings, transcriptions = self.parse_recordings_and_transcriptions(header_child)
                        header_item.setdefault("recordings", []).extend(recordings)
                        header_item.setdefault("transcriptions", []).extend(transcriptions)
                    case "dictionaryEntryHeaderAdditionalInformation":
                        header_item["additional_information"] = (
                            self.parse_header_additional_information(header_child)
                        )
                    case "hwcomma":
                        break
                    case _:
                        print(
                            f"[WARNING]: unknown class {cls} found when building header"
                        )
        header.append(header_item)
        return header

    def parse_header_additional_information(self, ai_node: scrapy.Selector):
        ai = {}
        for ai_child in ai_node.xpath("./*"):
            for cls in ai_child.attrib["class"].split():
                match cls:
                    case "starsForNumOccurrences":
                        ai["popularity"] = len(get_text_content(ai_child).strip())
                    case "languageVariety":
                        ai["language_variety"] = get_text_content(ai_child).strip()
                    case "languageRegister":
                        ai["language_register"] = get_text_content(ai_child).strip()
                    case _:
                        print(
                            f'[WARNING]: unknown item class "{cls}" found when building additional_information'
                        )
        return ai

    def parse_entity(self, entityEl: scrapy.Selector):
        entity = {"meaning_groups": []}
        meaning_group = None
        for child in entityEl.xpath("./*"):
            for cls in child.attrib["class"].split():
                match cls:
                    case "hws":
                        entity["header"] = self.parse_header(child.css(":scope > h1"))
                        note = child.css(":scope > .nt").get()
                        if note:
                            entity["note"] = note
                    case "dictpict":
                        entity["pictures"] = child.css(":scope > img").attrib["src"]
                    case "partOfSpeechSectionHeader":
                        if meaning_group:
                            entity['meaning_groups'].append(meaning_group)
                        meaning_group = {}
                        meaning_group["part_of_speech"] = get_text_content(
                            child.css(":scope > .partOfSpeech")
                        ).strip()
                    case "foreignToNativeMeanings":
                        if not meaning_group:
                            meaning_group = {}
                        elif 'meanings' in meaning_group:
                            entity['meaning_groups'].append(meaning_group)
                            meaning_group = {}
                        meaning_group["meanings"] = [self.parse_meaning(meaning_node) for meaning_node in child.css(":scope > li")]
                    case "vf":
                        meaning_group["forms"] = self.parse_forms(child)
                    case "additionalSentences":
                        continue
                    case _:
                        print(
                            f'[WARNING]: unknown item class "{cls}" found when building entity'
                        )
        entity['meaning_groups'].append(meaning_group)
        return entity

    def parse(self, response: scrapy.http.Response):
        for entity in response.xpath(
            '//*[@id="en-pl"]/../following-sibling::*[@class="diki-results-container"]/*[@class="diki-results-left-column"]/*/*[@class="dictionaryEntity"]'
        ):
            print(json.dumps(self.parse_entity(entity)))
