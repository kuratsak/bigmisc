#pragma once
#include <iostream>
#include <utility>
#include <functional>
#include <mutex>


template <typename CleanupFunc>
class ThreadUnsafeScopeGuard {
public:
    explicit ThreadUnsafeScopeGuard(CleanupFunc func)
        : cleanupFunc(std::move(func)), active(true) {
    }

    // Disable copy but allow move
    ThreadUnsafeScopeGuard(const ThreadUnsafeScopeGuard&) = delete;
    ThreadUnsafeScopeGuard& operator=(const ThreadUnsafeScopeGuard&) = delete;

    ThreadUnsafeScopeGuard(ThreadUnsafeScopeGuard&& other) noexcept
        : cleanupFunc(std::move(other.cleanupFunc)), active(other.active) {
        other.active = false;
    }

    ThreadUnsafeScopeGuard& operator=(ThreadUnsafeScopeGuard&& other) noexcept {
        if (this != &other) {
            cleanupFunc = std::move(other.cleanupFunc);
            active = other.active;
            other.active = false;
        }
        return *this;
    }

    ~ThreadUnsafeScopeGuard() {
        if (active) {
            cleanupFunc();
        }
    }

    // Disarm the guard explicitly if cleanup is not needed anymore
    void disarm() {
        active = false;
    }

private:
    CleanupFunc cleanupFunc;
    bool active;
};

//// Helper function for deduction
//template <typename CleanupFunc>
//ThreadUnsafeScopeGuard<CleanupFunc> makeThreadUnsafeScopeGuard(CleanupFunc func) {
//    return ThreadUnsafeScopeGuard<CleanupFunc>(std::move(func));
//}

template <typename CleanupFunc>
class ThreadSafeScopeGuard {
public:
    explicit ThreadSafeScopeGuard(CleanupFunc func)
        : cleanupFunc(std::move(func)), active(true) {
    }

    // Disable copy but allow move
    ThreadSafeScopeGuard(const ThreadSafeScopeGuard&) = delete;
    ThreadSafeScopeGuard& operator=(const ThreadSafeScopeGuard&) = delete;

    ThreadSafeScopeGuard(ThreadSafeScopeGuard&& other) noexcept {
        std::lock_guard<std::mutex> lock(other.mutex);
        cleanupFunc = std::move(other.cleanupFunc);
        active = other.active;
        other.active = false;
    }

    ThreadSafeScopeGuard& operator=(ThreadSafeScopeGuard&& other) noexcept {
        if (this != &other) {
            std::scoped_lock lock(mutex, other.mutex);
            cleanupFunc = std::move(other.cleanupFunc);
            active = other.active;
            other.active = false;
        }
        return *this;
    }

    ~ThreadSafeScopeGuard() {
        std::lock_guard<std::mutex> lock(mutex);
        if (active) {
            cleanupFunc();
        }
    }

    void disarm() {
        std::lock_guard<std::mutex> lock(mutex);
        active = false;
    }

private:
    CleanupFunc cleanupFunc;
    bool active;
    mutable std::mutex mutex; // Protect access to shared state
};

template<typename CleanupFunc>
using ScopeGuard = ThreadUnsafeScopeGuard<CleanupFunc>;


// Macro to create a unique ScopeGuard
#define ON_EXIT \
    auto ON_EXIT_UNIQUE_NAME = ScopeGuard

// Helper macro to concatenate tokens
#define MACRO_CONCAT(a, b) a##b

// Generate a unique name using __COUNTER__
#define ON_EXIT_UNIQUE_NAME \
    MACRO_CONCAT(scope_exit_guard_, __LINE__)