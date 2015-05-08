#!/usr/bin/env ruby

require 'webrick'

DOC_ROOT = ARGV[0] || "."
DEBUG = true

def debug(x)
  puts x if DEBUG
end

debug("DOC_ROOT = #{DOC_ROOT}")

s = WEBrick::HTTPServer.new(:Port => 8000,
    :DocumentRoot => DOC_ROOT)
trap("INT") {s.shutdown}

s.start
