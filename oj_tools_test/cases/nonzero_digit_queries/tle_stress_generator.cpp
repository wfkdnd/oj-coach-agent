#include <bits/stdc++.h>
using namespace std;

int main() {
    const int m = 200000;
    const int q = 200000;

    cout << string(m, '9') << '\n';
    cout << q << '\n';

    for (int i = 0; i < q; ++i) {
        cout << 0 << ' ' << m - 1 << '\n';
    }

    return 0;
}

