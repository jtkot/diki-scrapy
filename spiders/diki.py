import items
import json
import scrapy
from parsel.selector import SelectorList
from scrapy.selector.unified import Selector


def get_text_content(selector: Selector | SelectorList[Selector], recursive=True):
    return "".join(selector.xpath(".//text()" if recursive else "./text()").getall())


class DikiSpider(scrapy.Spider):
    name = "diki"

    async def start(self):
        urls = [
            "https://www.diki.pl/slownik-angielskiego?q=do",
        ]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    # Recording {
    # 	url: URL; OK
    #   lang: string OK
    # }

    # RecordingsAndTranscriptions {
    #     recordings?: Recording[]; OK
    #     transcriptions?: URL[]; OK
    # }
    def parse_recordings_and_transcriptions(self, rnt_node: Selector):
        rnt = items.Builder(items.RecordingsAndTranscriptions)
        for rnt_child in rnt_node.xpath("./*"):
            cls = rnt_child.attrib["class"].split()
            if "hasRecording" in cls:
                rnt.put(
                    "recordings",
                    items.Recording(
                        lang=rnt_child.attrib["class"].split()[0],
                        url=rnt_child.xpath("./*[@data-audio-url]").attrib[
                            "data-audio-url"
                        ],
                    ),
                )
            elif "phoneticTranscription" in cls:
                rnt.put(
                    "transcriptions",
                    rnt_child.xpath("./a/img").attrib["src"],
                )
            else:
                print(
                    f"[WARNING]: unknown class {cls} found during: parse_recordings_and_transcriptions"
                )
        return rnt.build()

    def parse_term(self, term_node: Selector):
        term = items.Builder(items.Term)
        term.put("value", get_text_content(term_node, False))
        for term_sibling in term_node.xpath("./following-sibling::*"):
            if term_sibling.root.tag == "a":
                break
            cls = term_sibling.attrib["class"].split()
            if "recordingsAndTranscriptions" in cls:
                term.put(
                    "recordings_and_transcriptions",
                    self.parse_recordings_and_transcriptions(term_sibling),
                )
            else:
                print(
                    f"[WARNING]: unknown class {cls} found during: parse_term"
                )
        return term.build()

    def parse_ref(self, ref_node: Selector):
        ref = items.Builder(items.Ref)
        ref.put("type", get_text_content(ref_node.xpath('./div'), False).strip()[:-1])
        for ref_child in ref_node.xpath("./div/a"):
            ref.put("terms", self.parse_term(ref_child))
        return ref.build()

    # Meaning {
    #     id: string; OK
    #     terms: string; OK
    #     not_for_children: boolean;
    #     additional_information?: AdditionalInformation; OK
    #     grammar_tags?: string[]; OK
    #     mf?: string; OK // TODO: figure out what actually that is
    #     example_sentences?: ExampleSentence[]; OK
    #     thematic_dictionaries?: string[]; OK
    #     note?: string; OK
    #     refs?: Ref[] OK;
    #     copyright?: string OK;
    # }
    def parse_meaning_partial(self, meaning_node: Selector, meaning_builder: items.Builder):
        for meaning_child in meaning_node.xpath("./*"):
            cls = meaning_child.attrib["class"].split()
            if "hw" in cls:
                meaning_builder.put("terms", get_text_content(meaning_child).strip())
            elif "grammarTag" in cls:
                meaning_builder.put(
                    "grammar_tags",
                    get_text_content(meaning_child).strip()[1:-1],
                )
            elif "meaningAdditionalInformation" in cls:
                meaning_builder.put(
                    "additional_information",
                    self.parse_additional_information(meaning_child)
                )
            elif "exampleSentence" in cls:
                meaning_builder.put(
                    "example_sentences",
                    self.parse_example_sentence(meaning_child),
                )
            elif "cat" in cls:
                meaning_builder.put(
                    "thematic_dictionaries",
                    get_text_content(meaning_child).strip(),
                )
            elif "ref" in cls:
                meaning_builder.put("refs", self.parse_ref(meaning_child))
            elif "nt" in cls:
                meaning_builder.put("note", get_text_content(meaning_child).strip())
            elif "mf" in cls:
                meaning_builder.put("mf", get_text_content(meaning_child).strip())
            elif "meaning_copyright" in cls:
                meaning_builder.put(
                    "copyright", get_text_content(meaning_child).strip()
                )
            elif "repetitionAddOrRemoveIconAnchor" in cls:
                pass
            else:
                print(f"[WARNING]: unknown class {cls} found during: parse_meaning_partial")
        return meaning_builder

    def parse_meaning(self, meaning_node: Selector):
        meaning = items.Builder(items.Meaning)
        meaning.put("id", meaning_node.attrib["id"][7:-3])
        not_for_children = False
        for meaning_child in meaning_node.xpath("./*"):
            cls = meaning_child.attrib["class"].split()
            if "hiddenNotForChildrenMeaning" in cls or "hiddenNotForChildrenMeaningExtras" in cls:
                not_for_children = True
                meaning = self.parse_meaning_partial(meaning_child, meaning)
            elif not_for_children:
                print(f"[WARNING]: unknown class {cls} found during: parse_meaning")
            else:
                meaning = self.parse_meaning_partial(meaning_node, meaning)
                break
        meaning.put("not_for_children", not_for_children)
        return meaning.build()
        # try:
        #     return meaning.build()
        # except:
        #     breakpoint()

    # Form {
    #     term: string; OK
    #     form: string; OK
    #     recordings_and_transcriptions?: RecordingsAndTranscriptions; OK
    # }
    def parse_form(self, root_node: Selector):
        form = items.Builder(items.Form)
        form.put("term", get_text_content(root_node).strip())
        for sibling in root_node.xpath("./following-sibling::*"):
            cls = sibling.attrib["class"].split()
            if "foreignTermText" in cls:
                break
            elif "foreignTermHeader" in cls:
                form.put("type", get_text_content(sibling).strip())
            elif "recordingsAndTranscriptions" in cls:
                form.put(
                    "recordings_and_transcriptions",
                    self.parse_recordings_and_transcriptions(sibling),
                )
            else:
                print(
                    f"[WARNING]: unknown class {cls} found during: parse_form"
                )
        return form.build()

    # ExampleSentence {
    #     sentence: string; OK
    #     translation: string; OK
    #     recordings_and_transcriptions?: RecordingsAndTranscriptions; OK
    # }
    def parse_example_sentence(self, es_node: Selector):
        es = items.Builder(items.ExampleSentence)
        es.put("sentence", get_text_content(es_node, False).strip())
        for es_child in es_node.xpath("./*"):
            cls = es_child.attrib["class"].split()
            if "exampleSentenceTranslation" in cls:
                es.put("translation", get_text_content(es_child).strip()[1:-1])
            elif "recordingsAndTranscriptions" in cls:
                es.put(
                    "recordings_and_transcriptions",
                    self.parse_recordings_and_transcriptions(es_child),
                )
            elif "repetitionAddOrRemoveIconAnchor" in cls:
                continue
            else:
                print(
                    f"[WARNING]: unknown class {cls} found during: parse_example_sequence"
                )
        return es.build()

    # Header {
    #     title: string; OK
    #     less_popular: boolean; OK)
    #     additional_information?: AdditionalInformation; OK
    #     recordings_and_transcriptions?: RecordingsAndTranscriptions; OK
    # }
    def parse_header(self, header_node: Selector):
        header = items.Builder(items.Header)
        less_popular = False
        header.put("title", get_text_content(header_node).strip())
        for header_sibling in header_node.xpath("./following-sibling::*"):
            if header_sibling.root.tag == "br":
                break
            cls = header_sibling.attrib["class"].split()
            if "hw" in cls:
                break
            elif "hwLessPopularAlternative" in cls:
                less_popular = True
            elif "recordingsAndTranscriptions" in cls:
                header.put(
                    "recordings_and_transcriptions",
                    self.parse_recordings_and_transcriptions(header_sibling),
                )
            elif "dictionaryEntryHeaderAdditionalInformation" in cls:
                header.put(
                    "additional_information",
                    self.parse_additional_information(header_sibling)
                )
            elif "hwcomma" in cls:
                continue
            else:
                print(
                    f"[WARNING]: unknown class {cls} found when building header"
                )
        header.put("less_popular", less_popular)
        return header.build()

    # AdditionalInformation {
    #     language_register?: string[]; OK
    #     language_variety?: string; OK
    #     other?: string;
    #     popularity?: number; OK
    # }
    def parse_additional_information(self, ai_node: Selector):
        ai = items.Builder(items.AdditionalInformation)
        other = get_text_content(ai_node, False).strip()
        if other: ai.put("other", other[1:-1])
        for ai_child in ai_node.xpath("./*"):
            cls = ai_child.attrib["class"].split()
            if "starsForNumOccurrences" in cls:
                ai.put("popularity", len(get_text_content(ai_child).strip()))
            elif "languageVariety" in cls:
                ai.put("language_variety", get_text_content(ai_child).strip())
            elif "languageRegister" in cls:
                ai.put("language_register", get_text_content(ai_child).strip())
            else:
                print(
                    f'[WARNING]: unknown item class "{cls}" found when building additional_information'
                )
        return ai.build()

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
    def parse_entity(self, entity_node: Selector):
        entity = items.Builder(items.DictionaryEntity)
        mg = items.Builder(items.MeaningGroup)
        for child in entity_node.xpath("./*"):
            cls = child.attrib["class"].split()
            if "hws" in cls:
                for header_node in child.xpath("./h1/*[@class='hw']"):
                    entity.put("headers", self.parse_header(header_node))
                note = child.xpath("./*[@class='nt']").get()
                if note:
                    entity.put("note", note)
            elif "partOfSpeechSectionHeader" in cls:
                mg.put("part_of_speech",
                    get_text_content(
                        child.xpath("./*[@class='partOfSpeech']")
                    ).strip(),
                )
            elif "vf" in cls:
                for form_node in child.xpath("./*[@class='foreignTermText']"):
                    mg.put("irregular_forms", self.parse_form(form_node))
            elif "foreignToNativeMeanings" in cls:
                for meaning_node in child.xpath("./li"):
                    mg.put("meanings", self.parse_meaning(meaning_node))
                entity.put("meaning_groups", mg.build())
                mg = items.Builder(items.MeaningGroup)
            elif "dictpict" in cls:
                entity.put("pictures", child.xpath("./img").attrib["src"])
            elif "additionalSentences" in cls:
                continue
            else:
                print(
                    f'[WARNING]: unknown item classes "{cls}" found when building entity'
                )
        return entity.build()

    # type: ignore[bad-override]
    def parse(self, response: scrapy.http.Response):
        i = 1
        for entity in response.xpath(
            '//*[@id="en-pl"]/../following-sibling::*[@class="diki-results-container"]/*[@class="diki-results-left-column"]/*/*[@class="dictionaryEntity"]'
        ):
            with open(f"do-{i}.json", "w") as f:
                json.dump(DikiSpider.parse_entity(self, entity), f)
                i += 1
