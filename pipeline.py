dofile("urlcode.lua")
dofile("table_show.lua")
JSON = (loadfile "JSON.lua")()

local item_type = os.getenv('item_type')
local item_value = os.getenv('item_value')
local item_dir = os.getenv('item_dir')
local warc_file_base = os.getenv('warc_file_base')

local items = {}
local disco = {}

local url_count = 0
local tries = 0
local downloaded = {}
local addedtolist = {}

for ignore in io.open("ignore-list", "r"):lines() do
  downloaded[ignore] = true
end

if item_type == "filelists" or item_type == "gets" or item_type == "files" then
  start, end_ = string.match(item_value, "([0-9]+)-([0-9]+)")
  for i=start, end_ do
    items[i] = true
  end
elseif item_type == "user" then
  items[item_value] = true
end

read_file = function(file)
  if file then
    local f = assert(io.open(file))
    local data = f:read("*all")
    f:close()
    return data
  else
    return ""
  end
end

allowed = function(url)
  if string.match(url, "'+")
     or string.match(url, "[<>\\]")
     or string.match(url, "//$") then
    return false
  end

  if string.match(url, "^https?://[^/]*ex%.ua/view/[0-9]+$")
     or string.match(url, "^https?://[^/]*ex%.ua/[0-9]+$") then
    return false
  end

  if (item_type == "filelists" or item_type == "gets" or item_type == "files")
     and string.match(url, "^https?://[^/]*ex%.ua/") then
    for s in string.gmatch(url, "([0-9]+)") do
      if items[tonumber(s)] == true then
        return true
      end
    end
  end

  return false
end

wget.callbacks.download_child_p = function(urlpos, parent, depth, start_url_parsed, iri, verdict, reason)
  local url = urlpos["url"]["url"]
  local html = urlpos["link_expect_html"]

  if (downloaded[url] ~= true and addedtolist[url] ~= true)
     and (allowed(url) or html == 0) then
    addedtolist[url] = true
    return true
  else
    return false
  end
end

wget.callbacks.get_urls = function(file, url, is_css, iri)
  local urls = {}
  local html = nil

  downloaded[url] = true
  
  local function check(urla)
    local origurl = url
    local url = string.match(urla, "^([^#]+)")
    if string.match(origurl, "^https?://[^/]*ex%.ua/r_view/[0-9]+$") and string.match(url, "^https?://f.+%?") then
      check(string.match(url, "^(.+)%?"))
    end
    if (downloaded[url] ~= true and addedtolist[url] ~= true)
       and (allowed(url)
       or (string.match(origurl, "^https?://[^/]*ex%.ua/r_view/[0-9]+$") and string.match(url, "^https?://f"))) then
      table.insert(urls, { url=string.gsub(url, "&amp;", "&") })
      addedtolist[url] = true
      addedtolist[string.gsub(url, "&amp;", "&")] = true
    end
  end

  local function checknewurl(newurl)
    if string.match(newurl, "^https?:////") then
      check(string.gsub(newurl, ":////", "://"))
    elseif string.match(newurl, "^https?://") then
      check(newurl)
    elseif string.match(newurl, "^https?:\\/\\?/") then
      check(string.gsub(newurl, "\\", ""))
    elseif string.match(newurl, "^\\/\\/") then
      check(string.match(url, "^(https?:)") .. string.gsub(newurl, "\\", ""))
    elseif string.match(newurl, "^//") then
      check(string.match(url, "^(https?:)") .. newurl)
    elseif string.match(newurl, "^\\/") then
      check(string.match(url, "^(https?://[^/]+)") .. string.gsub(newurl, "\\", ""))
    elseif string.match(newurl, "^/") then
      check(string.match(url, "^(https?://[^/]+)") .. newurl)
    end
  end

  local function checknewshorturl(newurl)
    if string.match(newurl, "^%?") then
      check(string.match(url, "^(https?://[^%?]+)") .. newurl)
    elseif not (string.match(newurl, "^https?:\\?/\\?//?/?")
       or string.match(newurl, "^[/\\]")
       or string.match(newurl, "^[jJ]ava[sS]cript:")
       or string.match(newurl, "^[mM]ail[tT]o:")
       or string.match(newurl, "^vine:")
       or string.match(newurl, "^android%-app:")
       or string.match(newurl, "^%${")) then
      check(string.match(url, "^(https?://.+/)") .. newurl)
    end
  end
  
  if allowed(url) then
    html = read_file(file)

    if string.match(url, "^https?://[^/]*ex%.ua/r_view/[0-9]+$")
       and string.match(html, "<author>([^<]+)</author>") then
      local author = string.match(html, "<author>([^<]+)</author>")
      local title = string.match(html, "<title>([^<]+)</title>")
      local object_id = string.match(url, "^https?://[^/]*ex%.ua/r_view/([0-9]+)$")
      disco[object_id] = {}
      disco[object_id]["author"] = author
      disco[object_id]["title"] = title
      disco[object_id]["files"] = {}
      for file in string.gmatch(html, "<file%s+([^>]+)/>") do
        local file_id = string.match(file, 'upload_id="([0-9]+)"')
        local file_md5 = string.match(file, 'md5="([0-9a-f]+)"')
        local file_size = string.match(file, 'size="([0-9]+)"')
        local file_name = string.match(file, 'name="([^"]+)"')
        disco[object_id]["files"][file_id] = {}
        disco[object_id]["files"][file_id]["md5"] = file_md5
        disco[object_id]["files"][file_id]["size"] = file_size
        disco[object_id]["files"][file_id]["name"] = file_name
      end
    end

    for newurl in string.gmatch(html, '([^"]+)') do
      checknewurl(newurl)
    end
    for newurl in string.gmatch(html, "([^']+)") do
      checknewurl(newurl)
    end
    for newurl in string.gmatch(html, ">%s*([^<%s]+)") do
      checknewurl(newurl)
    end
    for newurl in string.gmatch(html, "href='([^']+)'") do
      checknewshorturl(newurl)
    end
    for newurl in string.gmatch(html, 'href="([^"]+)"') do
      checknewshorturl(newurl)
    end
  end

  return urls
end
  

wget.callbacks.httploop_result = function(url, err, http_stat)
  status_code = http_stat["statcode"]
  
  url_count = url_count + 1
  io.stdout:write(url_count .. "=" .. status_code .. " " .. url["url"] .. ".  \n")
  io.stdout:flush()

  if (status_code >= 200 and status_code <= 399) then
    downloaded[url["url"]] = true
  end

  if item_type == "gets" and string.match(url["url"], "^https?://[^/]*ex%.ua/get/[0-9]+") then
    if status_code == 302 then
      return wget.actions.EXIT
    end
  end
  
  if status_code >= 500 or
    (status_code >= 400 and status_code ~= 404) or
    status_code == 0 then
    io.stdout:write("Server returned " .. http_stat.statcode .. " (" .. err .. "). Sleeping.\n")
    io.stdout:flush()
    os.execute("sleep 1")
    tries = tries + 1
    if tries >= 5 then
      io.stdout:write("\nI give up...\n")
      io.stdout:flush()
      tries = 0
      if allowed(url["url"]) then
        return wget.actions.ABORT
      else
        return wget.actions.EXIT
      end
    else
      return wget.actions.CONTINUE
    end
  end

  tries = 0

  local sleep_time = 0

  if sleep_time > 0.001 then
    os.execute("sleep " .. sleep_time)
  end

  return wget.actions.NOTHING
end

wget.callbacks.finish = function(start_time, end_time, wall_time, numurls, total_downloaded_bytes, total_download_time)
  local file = io.open(item_dir .. '/' .. warc_file_base .. '_data.txt', 'w')
  file:write(JSON:encode(disco))
  file:close()
end