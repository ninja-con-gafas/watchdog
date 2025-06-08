local json = require("cjson.safe")
local health_cache = ngx.shared.healthcheck_cache

local tcp = ngx.socket.tcp
local timeout = 1000  -- in ms
local cache_key = "server_health"

-- Required env vars
local server_ip = os.getenv("SERVER_IP")
local server_port = tonumber(os.getenv("SERVER_PORT"))
local gatekeeper_ip = os.getenv("HOST_IP")

-- Fallback route
local gatekeeper = "http://" .. gatekeeper_ip .. ":8501"
local target = gatekeeper

-- Load service config
local config_path = "/etc/openresty/services.json"
local file, err = io.open(config_path, "r")
if not file then
    ngx.log(ngx.ERR, "Failed to open services.json: ", err)
    return ngx.redirect(gatekeeper)
end

local config_data = file:read("*a")
file:close()

local service_map, decode_err = json.decode(config_data)
if not service_map then
    ngx.log(ngx.ERR, "Invalid JSON in services.json: ", decode_err)
    return ngx.redirect(gatekeeper)
end

-- Perform health check if cache is empty
local status = health_cache:get(cache_key)
if not status then
    local conn = tcp()
    conn:settimeout(timeout)

    local ok, connect_err = conn:connect(server_ip, server_port)
    if ok then
        health_cache:set(cache_key, "up", 15)
        status = "up"
        conn:close()
    else
        health_cache:set(cache_key, "down", 15)
        status = "down"
        ngx.log(ngx.ERR, "Server health check failed: ", connect_err)
    end
end

-- Check for valid service route if server is up
local host = ngx.var.host or ""
if status == "up" and service_map[host] then
    target = "http://" .. service_map[host].target
end

-- Redirect accordingly
return ngx.redirect(target)
