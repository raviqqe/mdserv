#!/usr/bin/env ruby

require 'webrick'

s = WEBrick::HTTPServer.new(:Port => 8000,
    :DocumentRoot => ".")
trap("INT") {s.shutdown}

s.start
