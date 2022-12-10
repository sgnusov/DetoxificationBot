messages = open("result").read().split('\n')
#messages = filter(lambda message: len(message.split()) > 1, messages)
open("processed_result", "w").write('\n'.join(messages))
