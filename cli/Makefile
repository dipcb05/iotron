CXX = g++
CXXFLAGS = -std=c++11 -Wall
SRC = src/main.cpp src/commands.cpp src/package_manager.cpp src/utils.cpp
OBJ = $(SRC:.cpp=.o)
EXEC = iotron-cli

all: $(EXEC)

$(EXEC): $(OBJ)
	$(CXX) $(OBJ) -o $(EXEC)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(OBJ) $(EXEC)

.PHONY: all clean
