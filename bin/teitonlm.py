#!/usr/bin/env python
#@Author Dulip Withanage
import subprocess
import shutil
from lxml import etree
from nlmmanipulate import NlmManipulate
from teimanipulate import TeiManipulate
from debug import Debuggable


class TeiToNlm (Debuggable):
    def __init__(self, gv):
        self.gv = gv
        self.module_name = "TEI to NLM"
        self.debug = gv.debug
        super(Debuggable, self).__init__()

    def saxon_tei2nlm(self):
            cmd = ["java", "-classpath", self.gv.java_class_path,
                   "-Dxml.catalog.files=" + self.gv.runtime_catalog_path,
                   "net.sf.saxon.Transform",
                   "-x", "org.apache.xml.resolver.tools.ResolvingXMLReader",
                   "-y", "org.apache.xml.resolver.tools.ResolvingXMLReader",
                   "-r", "org.apache.xml.resolver.tools.CatalogResolver",
                   "-o", self.gv.nlm_temp_file_path,
                   self.gv.tei_file_path,
                   self.gv.nlm_style_sheet_dir,
                   'autoBlockQuote=true'
                   ]
            return ' '.join(cmd)

    def run_quirks(self, process_ref_lists):
        manipulate = NlmManipulate(self.gv)
        if self.gv.settings.get_setting('linebreaks-as-comments', self) == 'False':
            # we need to convert every instance of <!--meTypeset:br--> to a new paragraph
            manipulate.close_and_open_tag('comment()[. = "meTypeset:br"]', 'p')

        # we will replace inside table cells and titles regardless because these are real JATS break tags
        manipulate.insert_break('comment()[. = "meTypeset:br"]', 'td')
        manipulate.insert_break('comment()[. = "meTypeset:br"]', 'title')

        manipulate.remove_empty_elements('//sec//p')

        if process_ref_lists:
            self.debug.print_debug(self, u'Finding potential reference lists')
            manipulate.find_reference_list()
            manipulate.tag_bibliography_refs()

        manipulate.handle_stranded_reference_titles_from_cues()

        manipulate.remove_empty_elements('//sec/list')
        manipulate.remove_empty_elements('//sec/disp-quote')

    def pre_cleanup(self):
        manipulate = TeiManipulate(self.gv)

        tree = manipulate.load_dom_tree()

        # make sure that head elements are not encapsulated within any elements that will stop them from being
        # correctly transformed by the XSL
        allowed = ['{http://www.tei-c.org/ns/1.0}div', '{http://www.tei-c.org/ns/1.0}body']

        head_elements = tree.xpath('//tei:div[tei:head]', namespaces={'tei': 'http://www.tei-c.org/ns/1.0'})

        count = 0

        for element in head_elements:
            current = element

            while current is not None:
                current = current.getparent()

                if current is not None:
                    if current.tag and current.tag not in allowed:
                        current.tag = 'REMOVE'
                        count += 1
                    elif current.tag and current.tag in allowed:
                        break
                else:
                    break

        if count > 0:
            etree.strip_tags(tree, 'REMOVE')
            manipulate.save_tree(tree)
            self.debug.print_debug(self, u'Extracted {0} headings from inside invalid elements'.format(count))

    def run_transform(self):
        self.pre_cleanup()

        self.gv.mk_dir(self.gv.nlm_folder_path)
        java_command = self.saxon_tei2nlm()
        self.debug.print_debug(self, u'Running saxon transform (TEI->NLM)')
        subprocess.call(java_command, stdin=None, shell=True)

        if self.gv.nlm_temp_file_path != self.gv.nlm_file_path:
            shutil.copy2(self.gv.nlm_temp_file_path, self.gv.nlm_file_path)

    def run(self, process_ref_lists, transform=True):
        if transform:
            self.run_transform()

        self.run_quirks(process_ref_lists)
