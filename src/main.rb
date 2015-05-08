#!/usr/bin/env ruby

require 'webrick'
require 'redcarpet'

require_relative 'config'


# global constants

DEBUG = true


# functions

def debug(x)
  puts x if DEBUG
end

def doc_root
  ARGV[0] || Config::DOC_ROOT
end

def make_html_file body
<<EOS
<!DOCTYPE html>
<html>
<head>
  <title></title>
  <link rel="stylesheet" href="/style.css" type="text/css"/>
  <!--
  <link rel="shortcut icon" href="/favicon.ico" type="image/x-icon"/>
  <link rel="icon" href="/favicon.ico" type="image/x-icon"/>
  <link rel="apple-touch-icon" href="/apple-touch-icon.png" type="image/png"/>
  -->
  <meta name="viewport" content="width=device-width"/>
</head>
<body>
#{body}
</body>
</html>
EOS
end

# classes

class MyMarkdown < String
  MD_PARSER = Redcarpet::Markdown.new(Redcarpet::Render::XHTML,
      autolink: true,
      fenced_code_blocks: true,
      quote: true,
      tables: true)

  def initialize text
    @text = text
  end

  def to_html
    return MD_PARSER.render(@text)
  end
end


# main routine

debug("DOC_ROOT = #{doc_root}")

s = WEBrick::HTTPServer.new(:Port => Config::PORT,
    :DocumentRoot => doc_root)
s.mount_proc("/") do |req, res|
  filename = File.expand_path(File.join(doc_root, *req.path.split("/")))
  if File.directory?(filename)
    filename = File.join(filename, "index.html")
  end

  if filename =~ /\.html$/ or filename =~ /\.htm$/
    res.body = make_html_file(MyMarkdown.new(open(filename.sub(/\.[^.]*$/,
        '.md')).read).to_html)
  elsif filename =~ /\.md$/
    res.body = open(filename).read
    res.content_type = "text/plain"
  else
    res.status = 404
  end
end

trap("INT") {s.shutdown}

s.start
