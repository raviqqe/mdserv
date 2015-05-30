#!/usr/bin/env python3

import http.server
import os
import os.path
import urllib.parse
import toml
import mistune
import getopt
import sys
import re



# the order of debug

DEBUG = True

def debug(x):
  if DEBUG:
    print("DEBUG:", x)



# global constants

CONFIG_FILE = "config.toml"
INDEX_MD = "index.md"



# global variables

g_config = None



# classes

class Config:
  """
  example of toml configuration file
  ```
  title = "my title"
  css = ["/style.css", "style.css"]
  icon = "/favicon.ico"
  phone_icon = "/apple-touch-icon.png"
  footer = "footer.html"
  valid_exts = [".md", ".py"]
  hidden_files = ["footer.html", "hidden.html"]
  """
  defaults = {
    "title" : "",
    "css" : [],
    "icon" : "",
    "phone_icon" : "",
    "footer" : "",
    "valid_exts" : [],
    "hidden_files" : [],
  }

  def __init__(self, config_file):
    self.conf_dict = toml.load(config_file)
    if ".md" in self.conf_dict["valid_exts"]:
      self.conf_dict["valid_exts"] += [".html", ".htm"]
    debug("Config.__init__(): self.config = {}".format(self.conf_dict))

  def __getitem__(self, key):
    debug("Config.__getitem__(): key = {}".format(key))
    if key in self.conf_dict:
      return self.conf_dict[key]
    else:
      return self.defaults[key]

  def __contains__(self, key):
    return key in self.conf_dict
    

class FileHandler(http.server.SimpleHTTPRequestHandler):
  def do_GET(self):
    """
      THIS FUNCTION INCLUDES CODES COPIED FROM PYTHON'S STANDARD LIBRARY
      Serve a GET request.
    """
    path = self.translate_path(self.path)
    assert os.path.isabs(path)
    debug("path = {}".format(path))
    if os.path.isdir(path):
      parts = urllib.parse.urlsplit(self.path)
      if not parts.path.endswith('/'):
        # redirect browser - doing basically what apache does
        self.send_response(301)
        new_parts = (parts[0], parts[1], parts[2] + '/',
                     parts[3], parts[4])
        new_url = urllib.parse.urlunsplit(new_parts)
        self.send_header("Location", new_url)
        self.end_headers()
        return
      else:
        self.write_response(os.path.join(path, "index.html"))
    else: # if path is a file
      self.write_response(path)

  def write_response(self, abs_path):
    """
      write response of HTTP response
    """
    assert os.path.isabs(abs_path)

    EXT = os.path.splitext(abs_path)[1]

    if not is_valid_path(abs_path) and os.path.splitext(abs_path)[1] != ".css":
      debug("write_response(): request to invalid file, {}".format(abs_path))
      self.send_404()
      return

    try:
      self.write_header(ctype=self.guess_type(abs_path))
      if os.path.basename(abs_path) in {"index.html", "index.htm"}:
        with open(change_ext2md(abs_path)) as f:
          self.wfile.write(make_html(
              print_navi(os.path.dirname(abs2rel(abs_path)))
              + md2html(f.read())
              + print_table_of_contents(os.path.dirname(abs_path))
              + print_footer()).encode())
      elif EXT in {".html", "htm"} and not os.path.isfile(abs_path):
        with open(change_ext2md(abs_path)) as f:
          self.wfile.write(make_html(
              print_navi(abs2rel(abs_path))
               + md2html(f.read()) + print_footer()).encode())
      else: # include .md files
        with open(abs_path, 'rb') as f:
          self.copyfile(f, self.wfile)
    except OSError:
      self.send_404()

  def write_header(self, ctype=None, length=None, mtime=None):
    self.send_response(200)
    if ctype:
      self.send_header("Content-type", ctype)
    if length != None:
      self.send_header("Content-Length", str(length))
    #self.send_header("Last-Modified",
    #    self.date_time_string(os.stat(abs_path).st_mtime))
    self.end_headers()

  def send_404(self):
    self.send_error(404, "File not found")


# functions

def abs2rel(abs_path):
  return "/" + os.path.relpath(abs_path, os.getcwd())


def md2html(markdown_text):
  return mistune.markdown(markdown_text, escape=True, use_xhtml=True)


def css_link(href):
  return '<link rel="stylesheet" href="{}" type="text/css"/>\n'.format(href)


def print_navi(path):
  return '<p><a href="{}">back</a></p><hr/>'.format(os.path.dirname(path))


def change_ext2md(path):
  return os.path.splitext(path)[0] + ".md"


def print_footer():
  if "footer" in g_config:
    with open(g_config["footer"]) as f:
      return f.read()
  else:
    return ""


def get_md_title(filename):
  with open(filename) as f:
    m = re.match(r"# *(.*)", f.read()) # somehow r"^# *(.*)$" doesn't work
    if m:
      return m.group(1)
    else:
      debug("get_md_title(): no md title found in {}".format(filename))
      return ""


def get_dir_title(dirname):
  if os.path.isfile(os.path.join(dirname, INDEX_MD)):
    INDEX_MD_TITLE = get_md_title(os.path.join(dirname, INDEX_MD))
    return INDEX_MD_TITLE if INDEX_MD_TITLE else os.path.basename(dirname)
  else:
    os.path.basename(dirname)


def is_valid_path(path):
  # path can be either relative or absolute
  return (os.path.splitext(path)[1] in g_config["valid_exts"]
      or os.path.isdir(path)) \
      and not (re.match(r"^\.", path) or re.match(r"/\.", path))


def li_anchor(href, text):
  return '<li><a href="{}">{}</a></li>'.format(href, text)


def print_table_of_contents(dir_path):
  assert os.path.isabs(dir_path)
  ret_str = "<h2>Table of Contents</h2><ul>"
  for node in [x for x in os.listdir(dir_path) if is_valid_path(x)
      and not os.path.basename(x) in g_config["hidden_files"]
      and not re.match(r"index\.(md)|(html)|(htm)", x)]:
    debug("print_table_of_contents(): " + "node = {}".format(node))
    REL_PATH = abs2rel(os.path.join(dir_path, node))
    EXT = os.path.splitext(node)[1]
    if os.path.isdir(node):
      ret_str += li_anchor(REL_PATH,
          get_dir_title(os.path.join(dir_path, node)))
    elif EXT == ".md" and EXT in g_config["valid_exts"]:
      MD_TITLE = get_md_title(os.path.join(dir_path, node))
      ret_str += li_anchor(REL_PATH.replace(".md", ".html"), # bad way
          MD_TITLE if MD_TITLE else node.replace(".md", ".html"))
    elif EXT in g_config["valid_exts"]:
      debug("print_table_of_contents() last if: " + "node = {}".format(node))
      ret_str += li_anchor(REL_PATH, node)
  return ret_str + "</ul>"


def make_html(body):
  BASE_DIR = "//cdnjs.cloudflare.com/ajax/libs/highlight.js/8.5"
  ret_str = """ <!DOCTYPE html>
      <html>
      <head>
        <title>""" + g_config["title"] + """</title>
        <meta name="viewport" content="width=device-width"/>
        <meta charset="utf-8"/>\n"""

  if g_config["css"]:
    ret_str += "\n".join(map(css_link, g_config["css"]))
  if g_config["icon"]:
    ret_str += ('<link rel="shortcut icon" href="{}" type="image/x-icon"/>\n'
        '<link rel="icon" href="{}" type="image/x-icon"/>\n') \
        .format(g_config["icon"], g_config["icon"])
  if g_config["phone_icon"]:
    ret_str += '<link rel="apple-touch-icon" href="{}" type="image/png"/>\n' \
        .format(g_config["phone_icon"])

  ret_str += """<link rel="stylesheet" href=""" + '"' +  BASE_DIR \
        + """/styles/default.min.css"/>
        <script src=""" + '"' + BASE_DIR + """/highlight.min.js"></script>
        <script>hljs.initHighlightingOnLoad();</script>
      </head>
      <body>
      <div class="markdown-body">
      """ + body + """
      </div>
      </body>
      </html>
      """
  return ret_str



# main routine

def main():
  global g_config
  DOC_ROOT = "."
  PORT = 80

  opts, args = getopt.getopt(sys.argv[1:], "d:p:")
  for option, value in opts:
    if option == "-d":
      DOC_ROOT = value
    elif option == "-p":
      assert value.isnumeric() and 0 <= int(value) <= 65535
      PORT = int(value)

  os.chdir(DOC_ROOT)
  # after this point, this server always works in the document root.

  if os.path.isfile(CONFIG_FILE):
    g_config = Config(CONFIG_FILE)

  server = http.server.HTTPServer(('', PORT), FileHandler)
  server.serve_forever()


if __name__ == "__main__":
  main()
