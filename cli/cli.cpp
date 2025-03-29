#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include "commands.h"
#include "package_manager.h"
#include "utils.h"

void displayHelp() {
    std::cout << "IoTron CLI - Command List" << std::endl;
    std::cout << "Usage: cli [command] [options]" << std::endl;
    std::cout << "\nAvailable Commands:" << std::endl;
    std::cout << "  install [package_name]    - Install a package" << std::endl;
    std::cout << "  uninstall [package_name]  - Uninstall a package" << std::endl;
    std::cout << "  update [package_name]     - Update a package" << std::endl;
    std::cout << "  list                      - List all installed packages" << std::endl;
    std::cout << "  network [protocol]        - Setup network protocols (e.g., mqtt, http)" << std::endl;
    std::cout << "  web install               - Install web dashboard" << std::endl;
    std::cout << "  protocols [type]          - Configure IoT protocol support" << std::endl;
    std::cout << "  help                      - Display this help message" << std::endl;
    std::cout << std::endl;
}

void parseArguments(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "No command provided! Use 'help' for usage." << std::endl;
        return;
    }

    std::string command = argv[1];

    if (command == "install") {
        if (argc < 3) {
            std::cerr << "Please specify a package to install!" << std::endl;
            return;
        }
        installPackage(argc, argv);
    } 
    else if (command == "uninstall") {
        if (argc < 3) {
            std::cerr << "Please specify a package to uninstall!" << std::endl;
            return;
        }
        uninstallPackage(argc, argv);
    }
    else if (command == "update") {
        if (argc < 3) {
            std::cerr << "Please specify a package to update!" << std::endl;
            return;
        }
        updatePackage(argc, argv);
    }
    else if (command == "list") {
        listPackages();
    }
    else if (command == "network") {
        if (argc < 3) {
            std::cerr << "Please specify a network protocol (e.g., mqtt, http)!" << std::endl;
            return;
        }
        setupNetworkProtocol(argc, argv);
    }
    else if (command == "web") {
        if (argc < 3) {
            std::cerr << "Use 'install' to install the web dashboard." << std::endl;
            return;
        }
        installWebDashboard();
    }
    else if (command == "protocols") {
        if (argc < 3) {
            std::cerr << "Please specify the protocol type!" << std::endl;
            return;
        }
        configureProtocol(argc, argv);
    }
    else if (command == "help") {
        displayHelp();
    }
    else {
        std::cerr << "Unknown command: " << command << std::endl;
        displayHelp();
    }
}

void installWebDashboard() {
    std::cout << "Installing Web Dashboard..." << std::endl;
    install("web-dashboard");
}

void setupNetworkProtocol(int argc, char* argv[]) {
    std::string protocol = argv[2];
    std::cout << "Setting up network protocol: " << protocol << std::endl;
    
    if (protocol == "mqtt") {
        std::cout << "Configuring MQTT..." << std::endl;
    } else if (protocol == "http") {
        std::cout << "Configuring HTTP..." << std::endl;
    } else if (protocol == "websocket") {
        std::cout << "Configuring WebSocket..." << std::endl;
    } else {
        std::cerr << "Unsupported protocol: " << protocol << std::endl;
    }
}

void configureProtocol(int argc, char* argv[]) {
    std::string protocol = argv[2];
    std::cout << "Configuring IoT protocol: " << protocol << std::endl;

    if (protocol == "i2c") {
        std::cout << "Configuring I2C..." << std::endl;
    } else if (protocol == "spi") {
        std::cout << "Configuring SPI..." << std::endl;
    } else if (protocol == "uart") {
        std::cout << "Configuring UART..." << std::endl;
    } else if (protocol == "can") {
        std::cout << "Configuring CAN..." << std::endl;
    } else {
        std::cerr << "Unsupported IoT protocol: " << protocol << std::endl;
    }
}

int main(int argc, char* argv[]) {
    std::cout << "Welcome to IoTron CLI!" << std::endl;
    parseArguments(argc, argv);
    return 0;
}
