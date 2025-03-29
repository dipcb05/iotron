#include "package_manager.h"
#include <iostream>

void install(std::string package) {
    std::cout << "Installing package: " << package << "..." << std::endl;
}

void uninstall(std::string package) {
    std::cout << "Uninstalling package: " << package << "..." << std::endl;
}

void update(std::string package) {
    std::cout << "Updating package: " << package << "..." << std::endl;
}
