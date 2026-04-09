#!/bin/sh
# Basic firewall script for MeTTaClaw

# Exit on error
set -e

echo "Setting up firewall..."

# Flush existing rules
iptables -F
iptables -X

# Set default policies (DROP everything)
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Allow established/related connections
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Allow DNS (UDP and TCP)
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# Allow HTTPS (443) for APIs
iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT

# Allow HTTP (80) if needed (e.g., for some web search)
iptables -A OUTPUT -p tcp --dport 80 -j ACCEPT

# Allow IRC if port is known (default 6667)
iptables -A OUTPUT -p tcp --dport 6667 -j ACCEPT

echo "Firewall configured. Starting application..."

# Execute the CMD passed to the container
exec "$@"
