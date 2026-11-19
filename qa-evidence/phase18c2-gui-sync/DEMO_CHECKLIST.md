# Phase 18C.2 GUI sync demo checklist

- Staging server: `http://127.0.0.1:58130`
- Work directory: `C:\Users\mrbin\AppData\Local\Temp\lg-18c2-demo-bv_rc7ul`
- [x] Login account A on Device A (settings + AccountLocalStore)
- [x] Add/edit vocabulary via study_data VocabStore facade
- [x] Login account A on Device B — vocabulary appears without import
- [x] Quiz attempts on A → Mistake Book / progress on B
- [x] Offline add converges after reconnect
- [x] Account B isolated
- [x] Preferences seeded/synced (contract v1)
- [x] Legacy import requires consent; guest JSON unchanged
- [x] Conflict list/resolve API exercised

Tkinter screens wired to `open_study_data()`: Vocabulary Library,
Quiz, Progress, Mistake Book, Daily Study, Reading/Listening add,
Home StudyMaster sync status + conflict/import dialogs.
