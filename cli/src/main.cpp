#include <iostream>
#include "commands.h"
#include "package_manager.h"
#include "utils.h"

int main(int argc, char* argv[]) {
    std::cout << "Welcome to IoTron" << std::endl;

    if (argc < 2) {
        std::cerr << "No command provided!" << std::endl;
        return 1;
    }

    std::string command = argv[1];
    if (command == "install") {
        installPackage(argc, argv);
    } else if (command == "list") {
        listPackages();
    } else {
        std::cerr << "Unknown command: " << command << std::endl;
        return 1;
    }

    return 0;
}