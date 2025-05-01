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
pass() {
    echo -e "${PASS}Test #$TEST_NUMBER: $1 PASS ✔${RESET}"
}

# Function to log failure messages in red
fail() {
    echo -e "${FAIL}Test #$TEST_NUMBER: $1 FAIL ✖ : Line ${BASH_LINENO[0]}${RESET}"
    FAILED_TEST_LIST+=("$TEST_NUMBER") # Add the failed test number to the list
}

# Start the sample HTTP server in the background
exec pipenv run python3 -m app.sample &
SERVER_PID=$!
echo "Started sample HTTP server with PID $SERVER_PID"
sleep 2  # Give the server time to start

######################################################## Tests

######################################################## Test - Validate 200 OK on root #####
((TEST_NUMBER++))

RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:8080)
BODY=$(echo "$RESPONSE" | head -n -1)
STATUS_CODE=$(echo "$RESPONSE" | tail -n 1)

if [ "$STATUS_CODE" -eq 200 ]; then
    pass "Got 200 OK on root"
else
    fail "Expected 200, but got $STATUS_CODE"
fi

######################################################## Test - Validate Content-Length header #####
((TEST_NUMBER++))

RESPONSE=$(curl -s -i -w "\n%{http_code}" http://localhost:8080)
HEADERS=$(echo "$RESPONSE" | sed -n '/^HTTP/,/^\r*$/p' | head -n -1)
BODY=$(echo "$RESPONSE" | sed -n '/^\r*$/,$p' | tail -n +2 | head -n -1)

# Extract the Content-Length header value
CONTENT_LENGTH=$(echo "$HEADERS" | grep -i "Content-Length" | awk '{print $2}' | tr -d '\r')

if [ "$CONTENT_LENGTH" -eq "${#BODY}" ]; then
    pass "Content-Length header matches the body length"
else
    fail "Content-Length header ($CONTENT_LENGTH) does not match the body length (${#BODY})"
fi

######################################################## Test - Validate 404 on an inexistent path #####
((TEST_NUMBER++))

RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:8080/ghiofgyuofg)
BODY=$(echo "$RESPONSE" | head -n -1)
STATUS_CODE=$(echo "$RESPONSE" | tail -n 1)

if [ "$STATUS_CODE" -eq 404 ]; then
    pass "Got 404 as expected"
else
    fail "Expected 404, but got $STATUS_CODE"
fi

######################################################## Test - Validate /test and /test/ are the same #####
((TEST_NUMBER++))

RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:8080/test)
RESPONSE2=$(curl -s -w "\n%{http_code}" http://localhost:8080/test/)
STATUS_CODE=$(echo "$RESPONSE" | tail -n 1)
STATUS_CODE2=$(echo "$RESPONSE2" | tail -n 1)

if [ "$STATUS_CODE" -eq 200 ] && [ "$STATUS_CODE2" -eq 200 ]; then
    pass "Got 200 OK on /test and /test/"
else
    fail "Got $STATUS_CODE on /test and $STATUS_CODE2 on /test/ expected was 200 on both"
fi

######################################################## Test - Validate dynamic segments #####
((TEST_NUMBER++))

RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:8080/echo/echo_test)
BODY=$(echo "$RESPONSE" | head -n -1)
STATUS_CODE=$(echo "$RESPONSE" | tail -n 1)

if [ "$STATUS_CODE" -eq 200 ] && [ "$BODY" == "echo_test!" ]; then
    pass "Got 200 OK and correct body on /echo/echo_test"
else
    fail "Got $STATUS_CODE and body '$BODY' on /echo/echo_test, expected 200 and 'echo_test!'"
fi

######################################################## Test - Validate query params #####
((TEST_NUMBER++))

RESPONSE=$(curl -s -w "\n%{http_code}" "http://localhost:8080/query?test=test1&test2=2")
BODY=$(echo "$RESPONSE" | head -n -1)
STATUS_CODE=$(echo "$RESPONSE" | tail -n 1)

if [ "$STATUS_CODE" -eq 200 ] && [ "$BODY" == "{'test': 'test1', 'test2': '2'}" ]; then
    pass "Got 200 OK and correct body on /query?test=test1&test2=2"
else
    fail "Got $STATUS_CODE and body '$BODY' on query?test=test1&test2=2, expected 200 and '{'test': 'test1', 'test2': '2'}'"
fi

######################################################## End of tests

# Stop the HTTP server
kill $SERVER_PID
echo -e "\nStopped HTTP server"

# Print summary of test results
echo -e "\nTest Summary:"
if [ "${#FAILED_TEST_LIST[@]}" -gt 0 ]; then
    echo -e "\t${FAIL}${#FAILED_TEST_LIST[@]} test(s) failed out of $TEST_NUMBER total tests.${RESET}" 
    echo -e "\t${FAIL}Failed tests: [${FAILED_TEST_LIST[*]}]${RESET}"
else
    echo -e "\t${PASS}All $TEST_NUMBER tests passed!${RESET}"
fi