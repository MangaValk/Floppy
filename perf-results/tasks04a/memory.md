# TASKS-04A — prefork child private memory

Separate variants are the median of five independent worker starts; the
merged control is two. Idle is measured in the child that runs the sync
body; PSS is unavailable on macOS. Total private memory is the sum of
each child's USS and its parent's RSS (parent USS unavailable).

| Variant | Idle child USS MiB | Idle child RSS MiB | Idle parent RSS MiB | Total private MiB |
| --- | ---: | ---: | ---: | ---: |
| baseline separate | 54.5 | 61.4 | 29.8 | 168.9 |
| after separate | 24.4 | 60.8 | 25.7 | 100.4 |
| after merged | 24.5 | 60.9 | 25.7 | 50.2 |

After vs baseline, separate: child USS -55.2%, child RSS -1.0%, total private -40.6%.

Peak during a full sync (median of 3/3 runs): USS 48.3 -> 44.9 MiB (-7.1%); RSS 56.6 -> 55.7 MiB (-1.7%).
