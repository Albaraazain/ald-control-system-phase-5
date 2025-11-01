# PLC Communication Guide

## 🎯 **Current Working Setup**

### **Network Configuration:**
- **Pi WiFi:** 10.5.5.x (Internet + Remote access via Tailscale)
- **Pi Ethernet:** 192.168.1.7 (PLC communication)
- **PLC IP:** 192.168.1.50 (Static)
- **Router:** 192.168.1.1 (Turkcell Superbox)

### **Connection Status:**
- ✅ **Remote Access:** Working via Tailscale
- ✅ **Internet Access:** Working via WiFi
- ✅ **PLC Communication:** Working via Ethernet
- ✅ **Dual Network:** Both networks active simultaneously

## 🚀 **Quick PLC Communication Commands**

### **Test PLC Connectivity**
```bash
# SSH to Pi from anywhere
ssh pi-remote

# Test PLC ping
ping -c 3 192.168.1.50

# Test PLC ports
telnet 192.168.1.50 502  # Modbus TCP
telnet 192.168.1.50 102  # Siemens S7
```

### **Monitor PLC Communication**
```bash
# Check network interfaces
ip addr show

# Check routing
ip route show

# Test both networks
ping -c 2 8.8.8.8        # Internet
ping -c 2 192.168.1.50   # PLC
```

## 🔧 **PLC Programming Setup**

### **Remote PLC Programming**
1. **SSH to Pi:** `ssh pi-remote`
2. **Install PLC software** on Pi (if needed)
3. **Configure PLC connection** to 192.168.1.50
4. **Program PLC remotely** from anywhere

### **Common PLC Software**
- **Siemens TIA Portal** (via Wine/VM)
- **Allen-Bradley Studio 5000** (via Wine/VM)
- **Modbus tools** (pymodbus, libmodbus)
- **OPC UA clients** (open62541, opcua)

## 📊 **Network Monitoring**

### **Check PLC Status**
```bash
# Test PLC connectivity
ssh pi-remote 'ping -c 3 192.168.1.50'

# Check PLC services
ssh pi-remote 'nmap -p 502,102 192.168.1.50'

# Monitor network traffic
ssh pi-remote 'tcpdump -i eth0 host 192.168.1.50'
```

### **PLC Data Collection**
```bash
# Example: Read Modbus data
ssh pi-remote 'python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((\"192.168.1.50\", 502))
print(\"PLC connected successfully\")
s.close()
"'
```

## 🛠️ **Troubleshooting PLC Communication**

### **If PLC Not Responding**
```bash
# Check network connectivity
ssh pi-remote 'ping -c 3 192.168.1.50'

# Check network interface
ssh pi-remote 'ip addr show eth0'

# Check routing
ssh pi-remote 'ip route show | grep 192.168.1'
```

### **If Internet Access Lost**
```bash
# Check WiFi interface
ssh pi-remote 'ip addr show wlan0'

# Test internet
ssh pi-remote 'ping -c 3 8.8.8.8'

# Restart networking
ssh pi-remote 'sudo systemctl restart dhcpcd'
```

### **If Remote Access Lost**
```bash
# Check Tailscale
tailscale status
tailscale ping pi

# Restart Tailscale
ssh pi-remote 'sudo systemctl restart tailscaled'
```

## 📱 **Mobile PLC Access**

### **Setup Mobile Access**
1. **Install Tailscale app** on phone/tablet
2. **Sign in** with same Google account
3. **Install SSH app** (Termius, Prompt, etc.)
4. **Connect:** `ssh atomicoat@100.100.138.5`
5. **Access PLC:** `ping 192.168.1.50`

### **Mobile PLC Programming**
- **SSH to Pi** from mobile
- **Use terminal-based tools** for PLC communication
- **Run PLC software** via SSH/X11 forwarding
- **Monitor PLC data** from anywhere

## 🔒 **Security Considerations**

### **Network Isolation**
- **PLC Network:** Isolated from internet (192.168.1.x)
- **Internet Network:** Separate from PLC (10.5.5.x)
- **Remote Access:** Encrypted via Tailscale VPN

### **Firewall Rules**
```bash
# Allow PLC communication
sudo ufw allow from 192.168.1.0/24

# Allow Tailscale
sudo ufw allow from 100.64.0.0/10

# Block other access
sudo ufw default deny incoming
```

## 🎯 **Best Practices**

### **1. Network Monitoring**
- **Regular ping tests** to PLC
- **Monitor network interfaces**
- **Check service status**

### **2. Backup Access**
- **Local network access** (when on same WiFi)
- **Physical access** (connect monitor/keyboard)
- **ngrok tunnel** (emergency access)

### **3. Documentation**
- **Document PLC IP and settings**
- **Keep network diagrams updated**
- **Record troubleshooting steps**

## ✅ **Verification Checklist**

### **Daily Checks**
- [ ] Remote access working: `ssh pi-remote`
- [ ] Internet access: `ping 8.8.8.8`
- [ ] PLC communication: `ping 192.168.1.50`
- [ ] Tailscale status: `tailscale status`

### **Weekly Checks**
- [ ] Network interfaces: `ip addr show`
- [ ] Service status: `sudo systemctl status ssh tailscaled`
- [ ] PLC connectivity: `telnet 192.168.1.50 502`
- [ ] Remote access: `tailscale ping pi`

---
*Your Pi now provides reliable remote access to PLCs with dual network capability!*
