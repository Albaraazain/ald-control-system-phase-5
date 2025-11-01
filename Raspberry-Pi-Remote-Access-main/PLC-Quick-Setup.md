# PLC Static IP - Quick Setup Guide

## 🎯 **YES! Your Pi can have both:**
- ✅ **Internet access** (for remote control)
- ✅ **Static IP** (for PLC communication)

## 🔧 **Three Setup Options:**

### **Option 1: Dual Interface (Recommended)**
- **WiFi:** Internet access (DHCP)
- **Ethernet:** PLC communication (static IP)

### **Option 2: USB Ethernet Adapter**
- **Built-in WiFi:** Internet access
- **USB Ethernet:** PLC communication (static IP)

### **Option 3: Single Interface with Static IP**
- **Ethernet:** Both internet and PLC (static IP)

## 🚀 **Quick Implementation:**

### **Step 1: Connect Hardware**
```bash
# Connect Ethernet cable to PLC network
# Keep WiFi connected for internet
```

### **Step 2: Configure Static IP**
```bash
# Edit network configuration
sudo nano /etc/dhcpcd.conf

# Add static IP for PLC communication
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4
```

### **Step 3: Apply Configuration**
```bash
# Restart networking
sudo systemctl restart dhcpcd

# Check configuration
ip addr show
```

### **Step 4: Test Connectivity**
```bash
# Test internet
ping -c 3 8.8.8.8

# Test PLC network
ping -c 3 192.168.1.1

# Test remote access
tailscale status
```

## 📋 **Common PLC Network Settings:**

### **Siemens S7-1200/1500**
- **IP Range:** 192.168.1.x
- **Subnet:** 255.255.255.0
- **Gateway:** 192.168.1.1

### **Allen-Bradley CompactLogix**
- **IP Range:** 192.168.1.x
- **Subnet:** 255.255.255.0
- **Gateway:** 192.168.1.1

### **Modbus TCP**
- **IP Range:** 192.168.1.x
- **Port:** 502
- **Subnet:** 255.255.255.0

## 🔧 **Example Configuration:**

```bash
# /etc/dhcpcd.conf
# WiFi for internet (DHCP)
interface wlan0
# No static configuration - uses DHCP

# Ethernet for PLC (Static IP)
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4
```

## ✅ **What You'll Have:**

### **Internet Access**
- ✅ **WiFi connection** for internet
- ✅ **Remote access** via Tailscale
- ✅ **SSH from anywhere** in the world

### **PLC Communication**
- ✅ **Static IP** for PLC network
- ✅ **Direct communication** with PLC
- ✅ **Reliable connection** for industrial protocols

### **Remote Management**
- ✅ **SSH access** from anywhere
- ✅ **PLC programming** remotely
- ✅ **Data logging** and monitoring

## 🛠️ **Implementation Steps:**

1. **Connect Ethernet** to PLC network
2. **Configure static IP** in dhcpcd.conf
3. **Restart networking** service
4. **Test connectivity** to PLC
5. **Verify internet access** still works
6. **Test remote access** via Tailscale

## 📱 **Remote Access Benefits:**

- **Monitor PLC** from anywhere
- **Program PLC** remotely
- **Collect data** from PLC
- **Troubleshoot** PLC issues
- **Update PLC** programs

## 🔒 **Security Features:**

- **Network isolation** (PLC network separate from internet)
- **Encrypted remote access** (Tailscale VPN)
- **Firewall rules** for protection
- **Secure authentication** (SSH keys)

---
*Your Pi will have both internet access and PLC communication with static IP!*
