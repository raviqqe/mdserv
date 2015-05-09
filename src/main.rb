#!/usr/bin/env ruby

require 'webrick'
require 'redcarpet'
require 'pathname'



# global constants

DOC_ROOT = Pathname.new(ARGV[0]).absolute? ? ARGV[0]
    : File.expand_path(File.join(Dir.pwd, ARGV[0]))
DEBUG = true


# functions

def debug(x)
  puts x if DEBUG
end


def make_html_file body
  base_dir="//cdnjs.cloudflare.com/ajax/libs/highlight.js/8.5"
<<EOS
<!DOCTYPE html>
<html>
<head>
  <title>
    #{(defined? Config::TITLE) ? Config::TITLE : "give me a name"}
  </title>
  <meta name="viewport" content="width=device-width"/>
  <!--
  <link rel="shortcut icon" href="/favicon.ico" type="image/x-icon"/>
  <link rel="icon" href="/favicon.ico" type="image/x-icon"/>
  <link rel="apple-touch-icon" href="/apple-touch-icon.png" type="image/png"/>
  -->
  #{(defined? Config::CSS) ? ('<link rel="stylesheet" href="' \
      + Config::CSS + '" type="text/css"/>') : ""}
  <link rel="stylesheet" href="#{base_dir}/styles/default.min.css"/>
  <script src="#{base_dir}/highlight.min.js"></script>
  <script>hljs.initHighlightingOnLoad();</script>
</head>
<body>
<div class="markdown-body">
#{body + print_footer}
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

def print_footer
  if defined? Config::FOOTER then open(Config::FOOTER).read else "" end
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

debug("DOC_ROOT = #{DOC_ROOT}")
Dir.chdir DOC_ROOT
require File.join(Dir.pwd, "config.rb")

s = WEBrick::HTTPServer.new(:Port => Config::PORT,
    :DocumentRoot => DOC_ROOT)
s.mount_proc("/") do |req, res|
  rel_path = req.path.sub(/\/index\.[^\/]*$/, "/")
  rel_path = rel_path.empty? ? "/" : rel_path
  abs_path = File.expand_path(File.join(DOC_ROOT, *rel_path.split("/")))

  if File.directory?(abs_path)
    res.body << <<EOS
<h1>#{rel_path}</h1>
<h2>Table of Contents</h2>
<ul>
EOS
    (Dir.entries(abs_path) - [".", ".."]).each do |file|
      if not defined? Config::INVALID_EXTS \
          or not Config::INVALID_EXTS.include? File.extname(file)
        file = file.sub(/\.md$/, ".html")
        res.body << <<EOS
<li><a href="#{File.join(rel_path, file)}"> #{file}</a></li>
EOS
      end
    end
    res.body << "</ul>"
    res.body = make_html_file(print_navi(rel_path) + res.body)
    res.content_type = "text/html"
  elsif abs_path =~ /\.html$/ or abs_path =~ /\.htm$/
    res.body << make_html_file(print_navi(rel_path) + MyMarkdown.new(
        open(abs_path.sub(/\.[^.]*$/, '.md')).read).to_html)
    res.content_type = "text/html"
  elsif abs_path =~ /\.md$/
    res.body << open(abs_path).read
    res.content_type = "text/plain"
  elsif abs_path =~ /\.css$/
    res.body << open(abs_path).read
    res.content_type = "text/css"
  else
    res.body = print_navi("/") + "404 you are lost now"
    res.status = 404
  end

end

trap("INT") {s.shutdown}

s.start
