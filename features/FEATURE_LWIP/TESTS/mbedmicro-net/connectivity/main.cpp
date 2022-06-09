/* mbed Microcontroller Library
 * Copyright (c) 2017 ARM Limited
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#if !FEATURE_LWIP
    #error [NOT_SUPPORTED] LWIP not supported for this target
#endif
#if DEVICE_EMAC
    #error [NOT_SUPPORTED] Not supported for WiFi targets
#endif

#include "mbed.h"
#include "greentea-client/test_env.h"
#include "unity.h"
#include "utest.h"

#include "EthernetInterface.h"

using namespace utest::v1;


// Bringing the network up and down
template <int COUNT>
void test_bring_up_down() {
    EthernetInterface eth;

    for (int i = 0; i < COUNT; i++) {
        int err = eth.connect();
        TEST_ASSERT_EQUAL(0, err);

        printf("MBED: IP Address %s\r\n", eth.get_ip_address());
        printf("MBED: Netmask %s\r\n", eth.get_netmask());
        printf("MBED: Gateway %s\r\n", eth.get_gateway());
        TEST_ASSERT(eth.get_ip_address());
        TEST_ASSERT(eth.get_netmask());
        TEST_ASSERT(eth.get_gateway());

        UDPSocket udp;
        err = udp.open(&eth);
        TEST_ASSERT_EQUAL(0, err);
        err = udp.close();
        TEST_ASSERT_EQUAL(0, err);

        TCPSocket tcp;
        err = tcp.open(&eth);
        TEST_ASSERT_EQUAL(0, err);
        err = tcp.close();
        TEST_ASSERT_EQUAL(0, err);

        err = eth.disconnect();
        TEST_ASSERT_EQUAL(0, err);
    }
}


// Test setup
utest::v1::status_t test_setup(const size_t number_of_cases) {
    GREENTEA_SETUP(120, "default_auto");
    return verbose_test_setup_handler(number_of_cases);
}

Case cases[] = {
    Case("Bringing the network up and down", test_bring_up_down<1>),
    Case("Bringing the network up and down twice", test_bring_up_down<2>),
};

Specification specification(test_setup, cases);

int main() {
    return !Harness::run(specification);
}
