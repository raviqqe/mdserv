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
  base_dir="//cdnjs.cloudflare.com/ajax/libs/highlight.js/8.5"
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
  <link rel="stylesheet" href="#{base_dir}/styles/rainbow.min.css"/>
  <script src="#{base_dir}/highlight.min.js"></script>
  <script>hljs.initHighlightingOnLoad();</script>
</head>
<body>
<div>
#{body}
</div>
</body>
</html>
EOS
end

def print_navi path
<<EOS
<p><a href="#{File.dirname(path)}">back</a></p>
<hr/>
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
  rel_path = req.path.sub(/\/index\.[^\/]*$/, "/")
  rel_path = rel_path.empty? ? "/" : rel_path
  abs_path = File.expand_path(File.join(doc_root, *rel_path.split("/")))

  res.body = print_navi rel_path

  if File.directory?(abs_path)
    res.body << <<EOS
<h1>#{rel_path}</h1>
<h2>Table of Contents</h2>
<ul>
EOS
    (Dir.entries(abs_path) - [".", ".."]).each do |file|
      file = file.sub(/\.md$/, ".html")
      res.body << <<EOS
<li><a href="#{File.join(rel_path, file)}"> #{file}</a></li>
EOS
    end
    res.body << "</ul>"
    res.content_type = "text/html"
  elsif abs_path =~ /\.html$/ or abs_path =~ /\.htm$/
    res.body << MyMarkdown.new(open(abs_path.sub(/\.[^.]*$/, '.md')).read)
        .to_html
    res.content_type = "text/html"
  elsif abs_path =~ /\.md$/
    res.body << open(abs_path).read
    res.content_type = "text/plain"
  else
    res.body = print_navi("/") + "404 you are lost now"
    res.status = 404
  end

  res.body = make_html_file(res.body)
end

trap("INT") {s.shutdown}

s.start
