#!/usr/bin/env python

import argparse
import http.server
import json
import os
import os.path
import urllib.parse
import mistune
import getopt
import sys
import re
import lxml.etree
import lxml.html
import abc
import mimetypes



CONFIG_FILE = "config.json"
ENCODING = "utf-8"
MARKDOWN_EXT = ".md"
INDEX_FILE = "index" + MARKDOWN_EXT



# the order of debug

DEBUG = True

def debug(*items):
  if DEBUG:
    info("DEBUG:", *items)

def info(*items):
  print(*items, file=sys.stderr)

def warn(*items):
  if DEBUG:
    error(*items)
  else:
    info("WARNING:", *items)

def error(*items):
  info("ERROR:", *items)
  exit(1)



class Config:
  # every item must be evaluated as False by bool() method
  DEFAULT_CONFIG = {
    "title" : "",
    "css" : [],
    "icon" : "",
    "phone_icon" : "",
    "copyright" : "",
    "valid_extensions" : [],
    "hidden_files" : [],
  }

  @staticmethod
  def _load_config_file(document_root):
    return load_json(os.path.join(document_root, CONFIG_FILE))

  @classmethod
  def _check_key_and_value(cls, key, value):
    if not isinstance(key, str):
      error("Keys must be a string.")

    if key not in cls.DEFAULT_CONFIG:
      error("Invalid key, '{}' detected in configuration file.".format(key))

    real_type = type(cls.DEFAULT_CONFIG[key])
    if not isinstance(value, real_type):
      error("Value of key, '{}' in configuration file must be {}."
            .format(key, real_type.__name__))

    if isinstance(cls.DEFAULT_CONFIG[key], list) \
       and not is_list_of_string(value):
      error("value of key, '{}' in configuration file must be a list of "
            "string.".format(key))

  def __init__(self, document_root):
    self._config_dict = self.DEFAULT_CONFIG

    for key, value in self._load_config_file(document_root).items():
      self._check_key_and_value(key, value)
      self._config_dict[key] = value

    self.valid_extensions.append(MARKDOWN_EXT)

    debug("self._config_dict = {}".format(self._config_dict))
    debug(self.valid_absolute_doc_paths)
    debug(self.valid_doc_basenames)

  def __getattr__(self, key):
    return self._config_dict[key]

  @property
  def _valid_doc_paths(self):
    return self.css + [self.copyright, self.icon, self.phone_icon]

  @property
  def valid_absolute_doc_paths(self):
    return {doc_path for doc_path in self._valid_doc_paths
            if doc_path.startswith('/')}

  @property
  def valid_doc_basenames(self):
    return {doc_path for doc_path in self._valid_doc_paths
            if not doc_path.startswith('/')}


class FileHandler(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
    debug("requested path =", self.path)

    if not is_safe_doc_path(self.path):
      self._send_404()
      return

    assert self.path.startswith('/')
    real_path = os.path.join(DOCUMENT_ROOT, self.path[1:])
    debug("requested real path = {}".format(real_path))
    if not os.path.exists(real_path):
      self._send_404()
      return

    if os.path.isdir(real_path) and not self.path.endswith('/'):
      self.send_response(301) # Moved Permanently
      self.send_header("Location", self.path + "/")
      self.end_headers()
      return

    self._send_reply(real_path)

  def _send_reply(self, real_path):
    assert os.path.isabs(real_path)
    assert is_safe_doc_path(abs2rel(real_path))

    index_file = os.path.join(real_path, INDEX_FILE)

    if os.path.isdir(real_path) and os.path.isfile(index_file):
      self._send_complete_header("text/html")
      self._send_index_file(index_file)
    elif is_markdown_file(real_path) and os.path.isfile(real_path):
      self._send_complete_header("text/html")
      self._send_md_file(real_path)
    elif os.path.isfile(real_path):
      self._send_complete_header(self._guess_type(real_path))
      self._send_other_file(real_path)
    else:
      self._send_404()

  def _send_other_file(self, filename):
    with open(filename, "rb") as file_:
      self.wfile.write(file_.read())

  def _send_index_file(self, md_file):
    self.wfile.write(HTML(
      HTMLNavigation(os.path.dirname(os.path.dirname(abs2rel(md_file)))),
      md2html(read_text_file(md_file)),
      HTMLTableOfContents(os.path.dirname(md_file)),
      HTMLElem(self._copyright(md_file)),
    ).to_str().encode(ENCODING))

  def _send_md_file(self, md_file):
    self.wfile.write(HTML(
      HTMLNavigation(os.path.dirname(abs2rel(md_file))),
      md2html(read_text_file(md_file)),
      HTMLElem(self._copyright(md_file))
    ).to_str().encode(ENCODING))

  def _send_complete_header(self, ctype):
    self.send_response(200)
    self.send_header("Content-type", ctype)
    self.end_headers()

  def _send_404(self):
    self.send_error(404, "I'm lost.")

  @staticmethod
  def _guess_type(path):
    return "text/html" if is_markdown_file(path) else \
           mimetypes.guess_type(path)[0]

  @staticmethod
  def _copyright(md_file):
    copyright_file = os.path.join(DOCUMENT_ROOT, CONFIG.copyright[1:]) \
                     if os.path.isabs(CONFIG.copyright) else \
                     os.path.join(os.path.dirname(md_file), CONFIG.copyright)

    if os.path.isfile(copyright_file):
      return read_text_file(copyright_file)
    return ""


class HTMLElem:
  def __init__(self, text):
    assert isinstance(text, str)
    self._text = text

  def to_str(self):
    return self._text


class HTMLTableOfContents(HTMLElem):
  def __init__(self, directory):
    assert os.path.isabs(directory)

    self._text = "<h2>Table of Contents</h2><ul>"

    for absolute_path in [os.path.join(directory, path)
                          for path in os.listdir(directory)
                          if not re.match(re.escape(INDEX_FILE), path)]:
      if not is_hidden_doc_path(abs2rel(absolute_path)) \
         and not (os.path.isdir(absolute_path)
                  and not os.path.isfile(os.path.join(absolute_path,
                                                      INDEX_FILE))):
        if is_markdown_file(absolute_path) and os.path.isfile(absolute_path):
          self._text += self.anchor_in_list_elem(
              abs2rel(absolute_path),
              get_md_title(absolute_path) or os.path.basename(absolute_path))
        elif os.path.isdir(absolute_path):
          self._text += self.anchor_in_list_elem(
              abs2rel(absolute_path),
              get_directory_title(absolute_path))
        else:
          self._text += self.anchor_in_list_elem(
              abs2rel(absolute_path),
              os.path.basename(absolute_path))

    self._text += "</ul>"

  @staticmethod
  def anchor_in_list_elem(href, name):
    return '<li><a href="{}">{}</a></li>'.format(href, name)


class HTMLNavigation(HTMLElem):
  def __init__(self, parent_directory_path):
    self._text = '<p><a href="{}">back</a></p><hr/>' \
                 .format(parent_directory_path)


class HTML:
  """
  complete HTML text
  """
  def __init__(self, *elems):
    assert all(isinstance(elem, HTMLElem) for elem in elems)

    self._text = '<!DOCTYPE html><html><head>' \
                 '<title>' + CONFIG.title + '</title>' \
                 '<meta name="viewport" content="width=device-width"/>' \
                 '<meta charset="utf-8"/>'

    if CONFIG.css:
      self._text += "\n".join(map(self._css_link, CONFIG.css))
    if CONFIG.icon:
      self._text += '<link rel="shortcut icon" href="{}" type="image/x-icon"/>'\
                    '<link rel="icon" href="{}" type="image/x-icon"/>' \
                    .format(CONFIG.icon, CONFIG.icon)
    if CONFIG.phone_icon:
      self._text += '<link rel="apple-touch-icon" href="{}" type="image/png"/>'\
                    .format(CONFIG.phone_icon)

    BASE_DIR = "//cdnjs.cloudflare.com/ajax/libs/highlight.js/8.5"
    self._text += '<link rel="stylesheet" href="' +  BASE_DIR + \
                  'styles/default.min.css"/>' \
                  '<script src="' + BASE_DIR + 'highlight.min.js"></script>' \
                  '<script>hljs.initHighlightingOnLoad();</script>' \
                  '</head>' \
                  '<body><div class="markdown-body">' \
                  + "".join(elem.to_str() for elem in elems) + \
                  '</div></body>' \
                  '</html>'

  def to_str(self):
    return lxml.etree.tostring(lxml.html.fromstring(self._text),
                               encoding=ENCODING,
                               doctype="<!DOCTYPE html>",
                               pretty_print=True).decode(ENCODING)

  @staticmethod
  def _css_link(href):
    return '<link rel="stylesheet" href="{}" type="text/css"/>'.format(href)


def is_markdown_file(filename):
  return file_extension(filename) == MARKDOWN_EXT


def file_extension(filename):
  return os.path.splitext(filename)[1]


def md2html(markdown_text):
  return HTMLElem(mistune.markdown(markdown_text, escape=True, use_xhtml=True))


def read_text_file(filename, mode="r"):
  with open(filename, mode, encoding=ENCODING) as file_:
    return file_.read()


def abs2rel(real_path):
  debug("abs2rel(): real_path =", real_path)
  doc_path = '/' + os.path.relpath(real_path, DOCUMENT_ROOT)
  debug("abs2rel(): doc_path =", doc_path)
  return doc_path


def get_md_title(filename):
  matched_text = re.match("# *(.*)", read_text_file(filename))
  if matched_text:
    return matched_text.group(1)
  info("get_md_title(): no md title found in {}".format(filename))
  return ""


def get_directory_title(directory):
  """
  Get the title of INDEX_FILE file in the directory.

  The directory must be a absolute path.
  """
  assert os.path.isabs(directory)

  md_file = os.path.join(directory, INDEX_FILE)
  if os.path.isfile(md_file):
    return get_md_title(md_file) or os.path.basename(directory)
  return os.path.basename(directory)


def is_safe_doc_path(path):
  """
  Check if path is unsafe or suspicious regarding accessing to hidden files,
  directory traversal attack and so on.

  Use this method to sanitize URLs.
  The paths must be requested paths in HTTP headers.
  """
  if re.match(r"\.\.", path):
    warn("directory tranersal attack detected in the request path, '{}'!"
         .format(path))
    return False

  if re.match(r"^\.[^/.]", path) or re.match(r"/\.[^/.]", path):
    debug("accesss to an unix hidden file is filtered in the request path, "
          "'{}'.".format(path))
    return False

  if path in CONFIG.valid_absolute_doc_paths \
      or os.path.basename(path) in CONFIG.valid_doc_basenames:
    return True

  extension = file_extension(path)
  if extension != "" and extension not in CONFIG.valid_extensions:
    debug("access to a file with invalid extenssion, '{}' is filtered "
          "in a request path, '{}'!".format(extension, path))
    return False
  return True


def is_list_of_string(list_of_string):
  if not isinstance(list_of_string, list):
    return False

  for string in list_of_string:
    if not isinstance(string, str):
      return False

  return True


def is_hidden_doc_path(path):
  if not is_safe_doc_path(path):
    return True
  elif path in CONFIG.hidden_files \
      or os.path.basename(path) in CONFIG.hidden_files:
    return True
  debug("is_hidden_doc_path(): passed path =", path)
  return False


def load_json(filename):
  with open(filename) as file_:
    return json.load(file_)


def serve(port):
  http.server.HTTPServer(('', port), FileHandler).serve_forever()


def check_args(args):
  if not os.path.isdir(args.document_root):
    raise FileNotFoundError("The document root directory, {} is not found."
                            .format(args.document_root))

  if not 0 <= args.port < 2 ** 16:
    raise ValueError("Invalid port number: {}".format(args.port))


def get_args():
  arg_parser = argparse.ArgumentParser()
  arg_parser.add_argument("-d", "--document-root", default=os.getcwd())
  arg_parser.add_argument("-p", "--port", type=int, default=80)
  args = arg_parser.parse_args()
  check_args(args)
  return args


def main():
  args = get_args()

  global DOCUMENT_ROOT
  DOCUMENT_ROOT = os.path.realpath(args.document_root)
  debug("DOCUMENT_ROOT =", DOCUMENT_ROOT)

  global CONFIG
  CONFIG = Config(DOCUMENT_ROOT)

  serve(args.port)


if __name__ == "__main__":
  main()
