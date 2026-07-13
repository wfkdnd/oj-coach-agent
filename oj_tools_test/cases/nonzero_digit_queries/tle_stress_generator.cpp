#include <iostream>
#include <fstream>
#include <string>
using namespace std;

static const long long MOD = 1000000007LL;

int main(int argc, char** argv) {
    int m = 50000;
    int q = 50000;
    const string inputFile = "tle_stress.in";
    const string outputFile = "tle_stress.out";

    if (argc >= 2) {
        m = stoi(argv[1]);
    }
    if (argc >= 3) {
        q = stoi(argv[2]);
    }
    if (m <= 0 || q <= 0) {
        cerr << "m and q must be positive\n";
        return 1;
    }

    ofstream input(inputFile);
    ofstream output(outputFile);
    if (!input || !output) {
        cerr << "failed to open output files\n";
        return 1;
    }

    string s(m, '9');
    input << s << '\n';
    input << q << '\n';
    for (int i = 0; i < q; ++i) {
        input << 0 << ' ' << m - 1 << '\n';
    }

    long long x = 0;
    for (int i = 0; i < m; ++i) {
        x = (x * 10 + 9) % MOD;
    }

    long long digitSum = 9LL * m % MOD;
    long long answer = x * digitSum % MOD;
    for (int i = 0; i < q; ++i) {
        if (i) {
            output << ' ';
        }
        output << answer;
    }
    output << '\n';

    cerr << "generated " << inputFile << " and " << outputFile
         << " with m=" << m << ", q=" << q << '\n';
    return 0;
}
