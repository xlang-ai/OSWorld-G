#!/bin/bash

# Define port range
start_index=3001
end_index=3002

# Function to install npm packages
install_npm() {
    folder="react-app-dir/react-app-$1"
    
    # Check if directory exists
    if [ -d "$folder" ]; then
        echo "Installing npm packages in $folder..."
        cd "$folder" || exit 1  # Change directory, exit if failed
        npm install  # Run npm install
        cd - > /dev/null  # Return to previous directory
    else
        echo "Directory $folder does not exist."
    fi
}

# Loop through each folder and run installations in parallel
for i in $(seq $start_index $end_index); do
    install_npm $i &  # Run each installation process in background
done

# Wait for all background processes to complete
wait

echo "All npm installs completed."
