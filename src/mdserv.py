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
  exit()



# global constants

CONFIG_FILE = "config.json"
ENCODING = "utf-8"
MARKDOWN_EXT = ".md"
INDEX_FILE = "index" + MARKDOWN_EXT



# global variables

g_config = None # dummy value
g_doc_root = "/this/is/just/a/dummy/value" # dummy value



# classes

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

  def __init__(self, document_root):
    self.config_dict = self.DEFAULT_CONFIG

    config_filename = os.path.join(document_root, CONFIG_FILE)
    if not os.path.isfile(config_filename):
      error("configuration file, '{}' not found in document root."
            .format(config_filename))

    for key, value in load_json(config_filename).items():
      assert type(key) == str
      if key not in self.DEFAULT_CONFIG:
        warn("invalid item, '{}' detected in configuration file, '{}'."
             .format(key, config_filename))
      elif type(self.DEFAULT_CONFIG[key]) == str \
           and not isinstance(self.config_dict[key], str):
        error("value of item, '{}' in configuration file must be string."
              .format(key))
      elif type(self.DEFAULT_CONFIG[key]) == list \
           and not self.is_list_of_string(self.config_dict[key]):
        error("value of item, '{}' in configuration file must be a list of "
              "string.".format(key))
      self.config_dict[key] = value

    if MARKDOWN_EXT in self.config_dict["valid_extensions"]:
      warn("'{}' is always included by mdserv as a valid extension. "
           .format(MARKDOWN_EXT), "you don't need to add it explicitly.")
    else:
      self.config_dict["valid_extensions"].append(MARKDOWN_EXT)

    self.set_valid_paths()

    debug("Config.__init__(): self.config_dict = {}".format(self.config_dict))

  def __getitem__(self, key):
    assert key in self.config_dict
    return self.config_dict[key]

  def set_valid_paths(self):
    valid_doc_paths = self.config_dict["css"] \
                      + [self.config_dict["copyright"],
                      self.config_dict["icon"],
                      self.config_dict["phone_icon"]]

    self.config_dict["valid_absolute_doc_paths"] \
        = {doc_path for doc_path in valid_doc_paths
          if doc_path.startswith('/')}
    self.config_dict["valid_doc_basenames"] \
        = {doc_path for doc_path in valid_doc_paths
          if not doc_path.startswith('/')}

    debug(self.config_dict["valid_absolute_doc_paths"])
    debug(self.config_dict["valid_doc_basenames"])

  @staticmethod
  def is_list_of_string(list_of_string):
    if type(list_of_string) == list:
      for string in list_of_string:
        if type(string) != str:
          return False
      return True
    else:
      return False


class FileHandler(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
    """
    serve a GET request.
    """
    debug("requested path =", self.path)

    if not is_safe_doc_path(self.path):
      self.send_404()
      return

    assert self.path.startswith('/')
    real_path = os.path.join(g_doc_root, self.path[1:])
    debug("requested real path = {}".format(real_path))
    if not os.path.exists(real_path):
      self.send_404()
      return

    if os.path.isdir(real_path):
      parts = urllib.parse.urlsplit(self.path)
      if not parts.path.endswith('/'):
        self.send_response(301) # Moved Permanently
        self.send_header("Location", urllib.parse.urlunsplit(
            (parts[0], parts[1], parts[2] + '/', parts[3], parts[4])))
        self.end_headers()
        return

    self.send_reply(real_path)

  def send_reply(self, real_path):
    """
    send HTTP reply.
    """
    assert os.path.isabs(real_path)
    assert is_safe_doc_path(abs2rel(real_path))

    if os.path.isdir(real_path) \
        and os.path.isfile(os.path.join(real_path, INDEX_FILE)):
      self.send_complete_header("text/html")
      self.send_index_md_file(os.path.join(real_path, INDEX_FILE))
    elif os.path.splitext(real_path)[1] == MARKDOWN_EXT \
        and os.path.isfile(real_path):
      self.send_complete_header("text/html")
      self.send_md_file(real_path)
    elif os.path.isfile(real_path):
      self.send_complete_header(self.guess_type(real_path))
      with open(real_path, "rb") as f:
        self.wfile.write(f.read())
    else:
      self.send_404()

  def send_index_md_file(self, md_file):
    with open_text_file(md_file) as f:
      self.wfile.write(HTML(HTMLContent(
          HTMLNavigation(os.path.dirname(os.path.dirname(abs2rel(md_file)))),
          md2html(f.read()),
          HTMLTableOfContents(os.path.dirname(md_file)),
          HTMLElem(self.copyright(md_file))))
          .to_str().encode(ENCODING))

  def send_md_file(self, md_file):
    with open_text_file(md_file) as f:
      self.wfile.write(HTML(HTMLContent(
          HTMLNavigation(os.path.dirname(abs2rel(md_file))),
          md2html(f.read()),
          HTMLElem(self.copyright(md_file))))
          .to_str().encode(ENCODING))

  def send_complete_header(self, ctype):
    self.send_response(200)
    self.send_header("Content-type", ctype)
    self.end_headers()

  def send_404(self):
    self.send_error(404, "I'm lost.")

  @staticmethod
  def guess_type(path):
    extension = os.path.splitext(path)[1]
    if extension == MARKDOWN_EXT:
      return "text/html"
    return mimetypes.guess_type(path)[0]

  @staticmethod
  def copyright(md_file):
    if os.path.isabs(g_config["copyright"]):
      copyright_file = os.path.join(g_doc_root, g_config["copyright"][1:])
    else:
      copyright_file = os.path.join(os.path.dirname(md_file),
                                    g_config["copyright"])
    if os.path.isfile(copyright_file):
      with open_text_file(copyright_file) as f:
        return f.read()
    else:
      return ""


class HTMLElem:
  def __init__(self, text):
    assert type(text) == str
    self.text = text

  def to_str(self):
    return self.text


class HTMLContent(HTMLElem):
  def __init__(self, *texts):
    self.text = ""
    for text in texts:
      assert isinstance(text, HTMLElem)
      self.text += text.to_str()


class HTMLTableOfContents(HTMLElem):
  def __init__(self, directory):
    assert os.path.isabs(directory)

    self.text = "<h2>Table of Contents</h2><ul>"

    for absolute_path in [os.path.join(directory, path)
        for path in os.listdir(directory)
        if not re.match(re.escape(INDEX_FILE), path)]:
      if not is_hidden_doc_path(abs2rel(absolute_path)) \
          and not (os.path.isdir(absolute_path)
          and not os.path.isfile(os.path.join(absolute_path, INDEX_FILE))):
        if os.path.splitext(absolute_path)[1] == MARKDOWN_EXT \
            and os.path.isfile(absolute_path):
          title = get_md_title(absolute_path)
          self.text += self.anchor_in_list_elem(abs2rel(absolute_path),
                                                title if title else
                                                abs2rel(absolute_path))
        elif os.path.isdir(absolute_path):
          self.text += self.anchor_in_list_elem(
              abs2rel(absolute_path),
              get_directory_title(absolute_path))
        else:
          self.text += self.anchor_in_list_elem(
              abs2rel(absolute_path),
              os.path.basename(absolute_path))

    self.text += "</ul>"

  @staticmethod
  def anchor_in_list_elem(href, name):
    return '<li><a href="{}">{}</a></li>'.format(href, name)


class HTMLNavigation(HTMLElem):
  def __init__(self, parent_directory_path):
    self.text = '<p><a href="{}">back</a></p><hr/>' \
                .format(parent_directory_path)


class HTML:
  """
  complete HTML text
  """
  def __init__(self, content):
    assert isinstance(content, HTMLContent)

    self.text = '<!DOCTYPE html><html><head>' \
                '<title>' + g_config["title"] + '</title>' \
                '<meta name="viewport" content="width=device-width"/>' \
                '<meta charset="utf-8"/>'

    if g_config["css"]:
      self.text += "\n".join(map(self.css_link, g_config["css"]))
    if g_config["icon"]:
      self.text += '<link rel="shortcut icon" href="{}" type="image/x-icon"/>'\
                   '<link rel="icon" href="{}" type="image/x-icon"/>' \
                   .format(g_config["icon"], g_config["icon"])
    if g_config["phone_icon"]:
      self.text += '<link rel="apple-touch-icon" href="{}" type="image/png"/>'\
                   .format(g_config["phone_icon"])

    BASE_DIR = "//cdnjs.cloudflare.com/ajax/libs/highlight.js/8.5"
    self.text += '<link rel="stylesheet" href="' +  BASE_DIR + \
                 'styles/default.min.css"/>' \
                 '<script src="' + BASE_DIR + 'highlight.min.js"></script>' \
                 '<script>hljs.initHighlightingOnLoad();</script>' \
                 '</head>' \
                 '<body><div class="markdown-body">' + content.to_str() + \
                 '</div></body>' \
                 '</html>'

    self.text = self.reformat_html(self.text)

  def to_str(self):
    debug("HTML:to_str(): type(self.text) =", type(self.text))
    return self.text

  @staticmethod
  def reformat_html(html_text):
    return lxml.etree.tostring(lxml.html.fromstring(html_text),
                               encoding=ENCODING,
                               doctype="<!DOCTYPE html>",
                               pretty_print=True).decode(ENCODING)

  @staticmethod
  def css_link(href):
    return '<link rel="stylesheet" href="{}" type="text/css"/>'.format(href)


# functions

def md2html(markdown_text):
  return HTMLElem(mistune.markdown(markdown_text,
                                   escape=True,
                                   use_xhtml=True))


def open_text_file(filename, mode="r"):
  return open(filename, mode=mode, encoding=ENCODING)


def abs2rel(real_path):
  debug("abs2rel(): real_path =", real_path)
  doc_path = '/' + os.path.relpath(real_path, g_doc_root)
  debug("abs2rel(): doc_path =", doc_path)
  return doc_path


def get_md_title(md_file):
  with open_text_file(md_file) as f:
    # somehow "^# *(.*)$" doesn't work
    matched_text = re.match("# *(.*)", f.read())
    if matched_text:
      return re.match(r"<p>(.*)</p>",
             md2html(matched_text.group(1)).to_str()).group(1)
    else:
      info("get_md_title(): no md title found in {}".format(md_file))
      return ""


def get_directory_title(directory):
  """
  Get the title of INDEX_FILE file in the directory.

  The directory must be a absolute path.
  """
  assert os.path.isabs(directory)

  md_file = os.path.join(directory, INDEX_FILE)
  if os.path.isfile(md_file):
    title = get_md_title(md_file)
    return title if title else os.path.basename(directory)
  else:
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

  if path in g_config["valid_absolute_doc_paths"] \
      or os.path.basename(path) in g_config["valid_doc_basenames"]:
    return True

  extension = os.path.splitext(path)[1]
  if extension != "" and extension not in g_config["valid_extensions"]:
    debug("access to a file with invalid extenssion, '{}' is filtered "
          "in a request path, '{}'!".format(extension, path))
    return False
  return True


def is_hidden_doc_path(path):
  if not is_safe_doc_path(path):
    return True
  elif path in g_config["hidden_files"] \
      or os.path.basename(path) in g_config["hidden_files"]:
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



# main routine

def main(*args):
  global g_config
  global g_doc_root

  args = get_args()

  g_doc_root = os.path.realpath(args.document_root)
  g_config = Config(g_doc_root)

  debug("main(): g_doc_root =", g_doc_root)

  serve(args.port)


if __name__ == "__main__":
  main(*sys.argv[1:])
