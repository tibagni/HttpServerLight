#!/bin/bash

# Define the colors
PASS='\033[0;32m'  # Green
FAIL='\033[0;31m'  # Red
RESET='\033[0m'    # No color

# Global variable to track the test number
TEST_NUMBER=0

# Record which tests failed so we can show at the end
FAILED_TESTS=()

# Function to log success messages in green
logPass() {
    echo -e "${PASS}Test #$TEST_NUMBER: $1 PASS ✔${RESET}"
}

# Function to log failure messages in red
logFail() {
    echo -e "${FAIL}Test #$TEST_NUMBER: $1 FAIL ✖${RESET}"
    FAILED_TEST_LIST+=("$TEST_NUMBER") # Add the failed test number to the list
}

# Start the sample HTTP server in the background
exec pipenv run python3 -m app.sample &
SERVER_PID=$!
echo "Started sample HTTP server with PID $SERVER_PID"
sleep 2  # Give the server time to start

##### Test 1 - Validate 200 OK on root #####
TEST_NUMBER=1

RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:8080)
BODY=$(echo "$RESPONSE" | head -n -1)
STATUS_CODE=$(echo "$RESPONSE" | tail -n 1)

if [ "$STATUS_CODE" -eq 200 ]; then
    logPass "Got 200 OK on root"
else
    logFail "Expected 200, but got $STATUS_CODE"
fi

##### Test 2 - Validate Content-Length header #####
TEST_NUMBER=2

RESPONSE=$(curl -s -i -w "\n%{http_code}" http://localhost:8080)
HEADERS=$(echo "$RESPONSE" | sed -n '/^HTTP/,/^\r*$/p' | head -n -1)
BODY=$(echo "$RESPONSE" | sed -n '/^\r*$/,$p' | tail -n +2 | head -n -1)

# Extract the Content-Length header value
CONTENT_LENGTH=$(echo "$HEADERS" | grep -i "Content-Length" | awk '{print $2}' | tr -d '\r')

if [ "$CONTENT_LENGTH" -eq "${#BODY}" ]; then
    logPass "Content-Length header matches the body length"
else
    logFail "Content-Length header ($CONTENT_LENGTH) does not match the body length (${#BODY})"
fi

##### Test 3 - Validate 404 on an inexistent path #####
TEST_NUMBER=3

RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:8080/ghiofgyuofg)
BODY=$(echo "$RESPONSE" | head -n -1)
STATUS_CODE=$(echo "$RESPONSE" | tail -n 1)

if [ "$STATUS_CODE" -eq 404 ]; then
    logPass "Got 404 as expected"
else
    logFail "Expected 404, but got $STATUS_CODE"
fi

# Print summary of test results
echo -e "\nTest Summary:"
if [ "${#FAILED_TEST_LIST[@]}" -gt 0 ]; then
    echo -e "\t${FAIL}${#FAILED_TEST_LIST[@]} test(s) failed out of $TEST_NUMBER total tests.${RESET}" 
    echo -e "\t${FAIL}Failed tests: [${FAILED_TEST_LIST[*]}]${RESET}"
else
    echo -e "\t${PASS}All tests passed!${RESET}"
fi

# Stop the HTTP server
kill $SERVER_PID
echo -e "\nStopped HTTP server"