#include "commands.h"
#include <iostream>

void installPackage(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Please specify a package to install!" << std::endl;
        return;
    }

    std::string package = argv[2];
    std::cout << "Installing package: " << package << std::endl;
    install(package);
}

void listPackages() {
    std::cout << "Listing installed packages..." << std::endl;
    std::cout << "Package 1, Package 2, Package 3" << std::endl;
}
