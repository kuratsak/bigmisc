#pragma once
// Performance counters inside any code block - modern C++ version by Dani Koretsky
#include <chrono>
#include <array>
#include "ScopeGuard.h"

#ifndef CUSTOM_DEBUG_MESSAGE
#include <windows.h>
#include <string>
void debugMessage(const std::string& message);
#endif

#define COUNT_BLOCK_PERFORMANCE() \
    PERF_START_PROLOG(); \
    ON_EXIT([&] { PERF_STOP_CLEANUP();}) \

// enable block performance counters
#ifndef ENABLE_PERF_TRACING
#define ENABLE_PERF_TRACING
#endif

#ifndef ENABLE_PERF_TRACING

#define PERF_TRACING_ENABLED 0
#define PERF_START_PROLOG()
#define PERF_STOP_CLEANUP()

#else
#define PERF_TRACING_ENABLED 1

constexpr uint32_t kMaxCountersBitmask = 0x1FF;
constexpr uint64_t kRoundsPerPrintBitmask = 0xF;

// measure execution time
// auto a = MilliCounter(); cout << "millis passed: " << a();
template<typename DurationType>
struct TimeCounter
{
    using Clock = std::chrono::high_resolution_clock;
    using TimePoint = Clock::time_point;
    TimePoint _start = Clock::now();
    TimePoint _end{ _start };
    TimePoint _last{ _start };
    inline void freeze() { _end = Clock::now(); }
    uint64_t operator() () {
        Clock::duration result = (_start == _end) ? (Clock::now() - _start) : (_end - _start);
        uint64_t elapsedTime = std::chrono::duration_cast<DurationType>(result).count();

        // performance counters
        rounds++;
        totalTime += elapsedTime;

        return elapsedTime;
    };
    uint64_t elapsedFromLastTime()
    {
        auto newPoint = Clock::now();
        Clock::duration result = (newPoint - _last);
        _last = newPoint;
        return std::chrono::duration_cast<DurationType>(result).count();
    }
    void reset() {
        _start = Clock::now();
        _end = _start;
        _last = _start;
    }

    uint64_t rounds = 0;
    uint64_t totalTime = 0;
    uint64_t threshold = kRoundsPerPrintBitmask;
};

using MilliCounter = TimeCounter<std::chrono::milliseconds>;
using MicroCounter = TimeCounter<std::chrono::microseconds>;
using SecondsCounter = TimeCounter<std::chrono::seconds>;

/*
The idea here:
    Lab code only (won't run in production), so indexing collisions are not a big deal -> move to __COUNTER__ to avoid all collisions!
    Log lines will show them (different blocks using same index)
    We want minimum overhead while tracing, so the index is compile time constant per block
    Shortest line has just 12 characters, we could always add more but then we might hit .cpp in some file names.

    Last update - raised to 0x3FF (1024) indexes to make room AND made many multiplications here to be unique
*/
#define LOG_LINE_ID(filename, linenumber) (std::string(filename) + "-" + std::to_string(linenumber))

// Generate a unique name using __COUNTER__
#define BLOCK_UNIQUE_ID() ((uint32_t)__COUNTER__ & kMaxCountersBitmask)

#define PERF_START_PROLOG() \
    /* setting identifiers for the log line printed when exiting the block scope */ \
    const auto kFilename = __FILE__; const auto kLineNumber = __LINE__; \
    bool isPerfTimingEnabled = PERF_TRACING_ENABLED; \
    uint32_t counterID = isPerfTimingEnabled ? BLOCK_UNIQUE_ID() : 0; \
    MicroCounter& counter = PerfCounters::getCounter(counterID); \
    if (isPerfTimingEnabled) { counter.reset(); }

#define PERF_STOP_CLEANUP() \
    if (isPerfTimingEnabled) \
    { \
        counter(); /* increments the total accumulated time */ \
        if (((counter.rounds & counter.threshold) == 0)) \
        { \
            counter.threshold = (counter.threshold << 1) | 1; \
            double averageTimes = static_cast<double>(counter.totalTime) / counter.rounds; \
            debugMessage(LOG_LINE_ID(kFilename, kLineNumber) + ": ID-" + std::to_string(counterID) + \
                " (calls, time, avg): " + std::to_string(counter.rounds) + "," + \
                std::to_string(counter.totalTime) + "," + std::to_string(averageTimes) \
            ); \
        } \
}

template<typename CounterType>
struct CounterArray
{
    static void initAll();
    static inline CounterType& getCounter(uint32_t id) { return _counters[id]; }

//private:
    static std::array<CounterType, kMaxCountersBitmask> _counters;
    static bool isInit;
};
#pragma message("defining alias for counter array")
using PerfCounters = CounterArray<MicroCounter>;
#endif