%Gets shell command return, plus the process if time limit is not met, returning timeout_error:
shell(Cmd, Out) :-
    tmp_file_stream(text, TmpFile, TmpInit),
    close(TmpInit),
    open(TmpFile, write, TmpOut, [type(text)]),
    catch(
        setup_call_cleanup(
            process_create(
                path(timeout),
                ['-k', '1s', '5s', 'sh', '-c', Cmd],
                [ stdout(stream(TmpOut)),
                  stderr(stream(TmpOut)),
                  process(P)
                ]
            ),
            (
                process_wait(P, Status),
                close(TmpOut),
                read_file_to_string(TmpFile, Text, [])
            ),
            (
                catch(close(TmpOut), _, true),
                catch(delete_file(TmpFile), _, true)
            )
        ),
        E,
        (
            catch(close(TmpOut), _, true),
            catch(delete_file(TmpFile), _, true),
            throw(E)
        )
    ),
    ( Status = exit(124) -> Out = timeout_error
    ; Status = exit(137) -> Out = timeout_error
    ; Status = killed(_) -> Out = timeout_error
    ; Out = Text
    ).


first_char(Str, C) :- sub_string(Str, 0, 1, _, C).
