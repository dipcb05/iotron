#include "utils.h"
#include <iostream>

void logAction(const std::string &action) {
    std::cout << "Action Log: " << action << std::endl;
}

void displayHelp() {
    std::cout << "IoTron CLI Commands:" << std::endl;
    std::cout << "  install [package_name] - Install a package" << std::endl;
    std::cout << "  list - List installed packages" << std::endl;
}
