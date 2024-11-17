// Experiments.cpp : This file contains the 'main' function. Program execution begins and ends there.
//

#include "pch.h"
#include "PerfTimer.h"

#if PERF_TRACING_ENABLED

template<>
std::array<MicroCounter, kMaxCountersBitmask> CounterArray<MicroCounter>::_counters = {};

template<>
bool CounterArray<MicroCounter>::isInit = false;

template<>
void CounterArray<MicroCounter>::initAll()
{
    if (!isInit)
    {
        _counters = {};
        isInit = true;
    }
}

#ifndef CUSTOM_DEBUG_MESSAGE
#pragma message("defining debug message")
void debugMessage(const std::string& message)
{
    // Convert std::string to a wide string
    std::wstring wideMessage(message.begin(), message.end());

    // Send the wide string to the debugger
    OutputDebugString(wideMessage.c_str());
}
#endif

#endif

// how to use
// #ifdef DEBUG_PERF_TRACING
//     PerfCounters::initAll();
// #endif

void test_func()
{
    COUNT_BLOCK_PERFORMANCE();

    constexpr uint64_t kUpdatePerIterations = 0x3FFFF;
    for (uint64_t i = 0; i < ((uint64_t)2 << 20); i++)
    {
        if (0 == (i & kUpdatePerIterations))
        {
            std::cout << "reached:" << i << "\n";
        }
    }
}

void test_func2()
{
    COUNT_BLOCK_PERFORMANCE();

    auto a = MicroCounter();
    //std::cout << "counter total" << a() << "\n";
    //for (uint64_t i = 0; i < ((uint64_t)2 << 20); i++)
    for (const auto i: std::views::iota(1, 10000))
    {
        a();
    }
}

int main()
{
#ifdef ENABLE_PERF_TRACING
    PerfCounters::initAll();
#endif
    debugMessage("test message debug");

    ON_EXIT([]() {std::cout << "exit hello\n";});
    std::cout << "Hello World!\n";
    for (const int i : std::views::iota(1, 35)) {
        test_func();
        test_func2();
    }
}

// Run program: Ctrl + F5 or Debug > Start Without Debugging menu
// Debug program: F5 or Debug > Start Debugging menu

// Tips for Getting Started: 
//   1. Use the Solution Explorer window to add/manage files
//   2. Use the Team Explorer window to connect to source control
//   3. Use the Output window to see build output and other messages
//   4. Use the Error List window to view errors
//   5. Go to Project > Add New Item to create new code files, or Project > Add Existing Item to add existing code files to the project
//   6. In the future, to open this project again, go to File > Open > Project and select the .sln file
