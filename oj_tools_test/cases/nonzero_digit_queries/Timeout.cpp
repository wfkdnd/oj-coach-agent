#include <bits/stdc++.h>
using namespace std;

static const long long MOD = 1000000007LL;

vector<long long> solveQueries(const string& s, const vector<pair<int, int>>& queries) {
    auto solendivar = make_pair(s, queries);
    (void)solendivar;

    vector<long long> answer;
    answer.reserve(queries.size());

    for (auto [left, right] : queries) {
        long long x = 0;
        long long digitSum = 0;

        for (int i = left; i <= right; ++i) {
            if (s[i] == '0') {
                continue;
            }

            int digit = s[i] - '0';
            x = (x * 10 + digit) % MOD;
            digitSum += digit;
        }

        answer.push_back(x * (digitSum % MOD) % MOD);
    }

    return answer;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string s;
    if (!(cin >> s)) {
        return 0;
    }

    int q;
    cin >> q;

    vector<pair<int, int>> queries(q);
    for (auto& [left, right] : queries) {
        cin >> left >> right;
    }

    vector<long long> answer = solveQueries(s, queries);
    for (int i = 0; i < (int)answer.size(); ++i) {
        if (i) {
            cout << ' ';
        }
        cout << answer[i];
    }
    cout << '\n';

    return 0;
}

