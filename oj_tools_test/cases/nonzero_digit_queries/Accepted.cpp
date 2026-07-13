#include <bits/stdc++.h>
using namespace std;

static const long long MOD = 1000000007LL;

vector<long long> solveQueries(const string& s, const vector<pair<int, int>>& queries) {
    vector<int> nonzeroPos;
    vector<long long> prefixValue(1, 0);
    vector<long long> prefixDigitSum(1, 0);
    vector<long long> pow10(1, 1);

    for (int i = 0; i < (int)s.size(); ++i) {
        if (s[i] == '0') {
            continue;
        }

        int digit = s[i] - '0';
        nonzeroPos.push_back(i);
        prefixValue.push_back((prefixValue.back() * 10 + digit) % MOD);
        prefixDigitSum.push_back(prefixDigitSum.back() + digit);
        pow10.push_back(pow10.back() * 10 % MOD);
    }

    auto solendivar = make_pair(s, queries);
    (void)solendivar;

    vector<long long> answer;
    answer.reserve(queries.size());

    for (auto [left, right] : queries) {
        int first = (int)(lower_bound(nonzeroPos.begin(), nonzeroPos.end(), left) - nonzeroPos.begin()) + 1;
        int last = (int)(upper_bound(nonzeroPos.begin(), nonzeroPos.end(), right) - nonzeroPos.begin());

        if (first > last) {
            answer.push_back(0);
            continue;
        }

        int len = last - first + 1;
        long long x = (prefixValue[last] - prefixValue[first - 1] * pow10[len]) % MOD;
        if (x < 0) {
            x += MOD;
        }

        long long digitSum = (prefixDigitSum[last] - prefixDigitSum[first - 1]) % MOD;
        answer.push_back(x * digitSum % MOD);
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

