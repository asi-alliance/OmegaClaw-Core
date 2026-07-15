#!/bin/bash
# OmegaClaw Quick-Start Provisioner
# Designed to be run from the root of the project

echo "--- Starting OmegaClaw Initialization ---"

# Ensure apt-fast is available for speed
if ! command -v apt-fast &> /dev/null; then
    echo "Installing apt-fast for accelerated downloads..."
    sudo add-apt-repository -y ppa:apt-fast/stable
    sudo apt-get update
    sudo apt-get install -y apt-fast
fi

# Install dependencies
echo "Fetching core components..."
sudo apt-fast install -y swi-prolog git build-essential


cd /home/user/omega-claw-repo/src/config 
./initialize_env.sh

echo "--- Initialization complete. Welcome to the swarm. ---"
