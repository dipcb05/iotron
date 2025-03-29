#ifndef PACKAGE_MANAGER_H
#define PACKAGE_MANAGER_H

#include <string>

void install(std::string package);
void uninstall(std::string package);
void update(std::string package);

#endif