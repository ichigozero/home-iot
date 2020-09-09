import wifimgr

wlan = wifimgr.get_connection()

if wlan is None:
    print('Could not initialize the network connection.')

    # Start web server for connection manager
    wifimgr.start()

# Main Code goes here, wlan is a working network.WLAN(STA_IF) instance.
print('ESP OK')
