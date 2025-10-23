#include <iostream>
#include <vector>
#include <type_traits>

template<typename T>
struct HasSerialize {
    template<typename U>
    static auto test(int) -> decltype(std::declval<U>().serialize(), std::true_type{});
    
    template<typename>
    static std::false_type test(...);
    
    static constexpr bool value = decltype(test<T>(0))::value;
};

template<typename T, typename Enable = void>
struct Serializer {
    static void serialize(const T& obj) {
        static_assert(HasSerialize<T>::value, "Type must have serialize() method");
    }
};

template<typename Container>
struct Serializer<Container, typename std::enable_if<
    std::is_same<typename Container::value_type, int>::value
>::type> {
    static void serialize(const Container& container) {
        for (const auto& item : container) {
            std::cout << item << " ";
        }
    }
};

struct MyData {
    int x;
    double y;
    std::string name;
};

template<typename T, typename U, typename V>
struct TripleContainer {
    T first;
    U second;
    V third;
    
    void serializeAll() {
        Serializer<T>::serialize(first);
        Serializer<U>::serialize(second);
        Serializer<V>::serialize(third);
    }
};

int main() {
    std::vector<int> vec = {1, 2, 3};
    MyData data{10, 3.14, "test"};
    
    TripleContainer<std::vector<int>, MyData, double> container;
    container.first = vec;
    container.second = data;
    container.third = 2.718;
    
    container.serializeAll();  // ERROR: MyData and double don't have serialize()
    
    return 0;
}