%Gets shell command return via safe_shell_runner.py which uses process groups for reliable timeout:
:- prolog_load_context(directory, Dir), asserta(skills_dir(Dir)).

shell(Cmd, Out) :- atom_string(Cmd, CmdStr),
                   skills_dir(Dir),
                   atomic_list_concat([Dir, '/safe_shell_runner.py'], RunnerPath),
                   atomic_list_concat(['python3 ', RunnerPath, ' --timeout 5 "', CmdStr, '"'], SafeCmd),
                   process_create(path(sh), ['-c', SafeCmd], [ stdout(pipe(S)), stderr(pipe(SE)), process(P)]),
                   setup_call_cleanup(true,
                                      read_string(S, _, Text),
                                      close(S)),
                   close(SE),
                   process_wait(P, Status),
                   ( Status = exit(0) -> Out = Text
                                       ; Out = timeout_error ).

first_char(Str, C) :- sub_string(Str, 0, 1, _, C).
