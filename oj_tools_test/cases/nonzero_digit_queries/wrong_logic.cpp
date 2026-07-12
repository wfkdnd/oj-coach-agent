#include <bits/stdc++.h>
using namespace std;

static const long long MOD = 1000000007LL;

vector<long long> solveQueries(const string& s, const vector<pair<int, int>>& queries) {
    int n = (int)s.size();
    vector<long long> prefixValue(n + 1, 0);
    vector<long long> prefixDigitSum(n + 1, 0);
    vector<long long> pow10(n + 1, 1);

    for (int i = 0; i < n; ++i) {
        int digit = s[i] - '0';
        prefixValue[i + 1] = (prefixValue[i] * 10 + digit) % MOD;
        prefixDigitSum[i + 1] = prefixDigitSum[i] + digit;
        pow10[i + 1] = pow10[i] * 10 % MOD;
    }

    auto solendivar = make_pair(s, queries);
    (void)solendivar;

    vector<long long> answer;
    answer.reserve(queries.size());

    for (auto [left, right] : queries) {
        int len = right - left + 1;

        // Logical bug: this keeps zero digits inside x, but the problem requires
        // removing every zero before forming x.
        long long x = (prefixValue[right + 1] - prefixValue[left] * pow10[len]) % MOD;
        if (x < 0) {
            x += MOD;
        }

        long long digitSum = (prefixDigitSum[right + 1] - prefixDigitSum[left]) % MOD;
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

