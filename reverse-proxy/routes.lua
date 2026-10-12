local json = require("cjson.safe")
local health_cache = ngx.shared.healthcheck_cache

local tcp = ngx.socket.tcp
local timeout = 1000  -- in ms
local gatekeeper_ip = os.getenv("HOST_IP")
local default_gatekeeper = "http://" .. gatekeeper_ip .. ":8501"

-- Load service configuration
local config_path = "/etc/openresty/services.json"
local file, err = io.open(config_path, "r")
if not file then
    ngx.log(ngx.ERR, "Failed to open services.json: ", err)
    return ngx.redirect(default_gatekeeper)
end

local config_data = file:read("*a")
file:close()

local config, decode_err = json.decode(config_data)
if not config or not config.routes or not config.nodes then
    ngx.log(ngx.ERR, "Invalid configuration format in services.json: ", decode_err)
    return ngx.redirect(default_gatekeeper)
end

local host = ngx.var.host or ""
local route = config.routes[host]

if not route then
    ngx.log(ngx.ERR, "No route found for host: ", host)
    return ngx.redirect(default_gatekeeper)
end

local node_key = route.node
local node = config.nodes[node_key]

if not node then
    ngx.log(ngx.ERR, "No node configuration found for key: ", tostring(node_key))
    return ngx.redirect(default_gatekeeper)
end

local node_gatekeeper_url = default_gatekeeper .. "/?node=" .. node_key
local cache_key = "health:" .. node.ip .. ":" .. tostring(node.health_port)

-- Perform TCP health check if cache is empty
local status = health_cache:get(cache_key)
if not status then
    local conn = tcp()
    conn:settimeout(timeout)

    local ok, connect_err = conn:connect(node.ip, node.health_port)
    if ok then
        health_cache:set(cache_key, "up", 15)
        status = "up"
        conn:close()
    else
        health_cache:set(cache_key, "down", 15)
        status = "down"
        ngx.log(ngx.ERR, "Node health check failed for ", node.ip, ": ", connect_err)
    end
end

-- Redirect to target if UP, otherwise redirect to Gatekeeper UI with node parameter
if status == "up" then
    return ngx.redirect("http://" .. route.target)
else
    return ngx.redirect(node_gatekeeper_url)
end