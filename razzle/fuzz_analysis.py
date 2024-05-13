import argparse
from TransBodyBlock import TriggerType
from TransTrainBlock import TrainType
from TransVictimBlock import SecretMigrateType
from TransBlockUtils import BaseBlockType
from FuzzManager import FuzzResult
from payload.MagicDevice import Instruction

class RecordAnalysis:
    def __init__(self, input_file, output_file):
        self.input_file = input_file
        self.output_file = output_file
        self.token_list = []
        self.token = None
        self.field = None
    
    def token_generate(self):
        for line in open(self.input_file, 'rt'):
            token_list = line.strip().split()
            self.token_list.extend(token_list)

    def next_token(self):
        if len(self.token_list) == 0:
            return None
        elif self.token != None:
            return self.token
        else: 
            self.token = self.token_list.pop(0)
            return self.token

    def eat_token(self):
        assert self.token is not None
        self.token = None
    
    def next_field(self):
        if self.field is not None:
            return self.field
        
        token = self.next_token()
        if token is None:
            return None
        assert token.endswith(':')
        self.field = (token[:-1], [])
        self.eat_token()

        while True:
            token = self.next_token()
            if token is None:
                return self.field
            if token.endswith(':'):
                return self.field
            self.field[1].append(token)
            self.eat_token()
    
    def eat_field(self):
        assert self.field is not None
        self.field = None

    def parse_header(self):
        header_record = {}
        field = self.next_field()
        if field is None:
            return None
        if field[0] != 'iter_num':
            return None

        while True:
            field = self.next_field()
            if field is None:
                break
            key = field[0]
            value_seq = field[1]
            if key == 'train' or key == 'victim' or key == 'result':
                break
            header_record[key] = eval(value_seq[0])
            self.eat_field()
        return header_record
    
    def parse_result(self):
        result_record = {}
        field = self.next_field()
        if field is None:
            return None
        if field[0] != 'result':
            return None

        while True:
            field = self.next_field()
            if field is None:
                break
            key = field[0]
            value_seq = field[1]
            if key == 'train' or key == 'victim' or key == 'iter_num':
                break
            if key == 'encode_fuzz_type':
                result_record[key] = value_seq[0]
            else:
                result_record[key] = eval(value_seq[0])
            self.eat_field()
        return result_record

    def parse_train(self):
        train_record = {}
        field = self.next_field()
        if field is None:
            return None
        if field[0] != 'train':
            return None

        while True:
            field = self.next_field()
            if field is None:
                break
            key = field[0]
            value_seq = field[1]
            if key == 'result' or key == 'victim' or key == 'iter_num':
                break
            if key == 'train_inst':
                train_record[key] = Instruction(' '.join(value_seq))
            else:
                train_record[key] = eval(value_seq[0])
            self.eat_field()
        return train_record
    
    def parse_victim(self):
        victim_record = {}
        field = self.next_field()
        if field is None:
            return None
        if field[0] != 'victim':
            return None

        while True:
            field = self.next_field()
            if field is None:
                break
            key = field[0]
            value_seq = field[1]
            if key == 'train' or key == 'result' or key == 'iter_num':
                break
            if key == 'trigger_inst':
                if victim_record['trigger_type'] == TriggerType.ILLEGAL:
                    inst = Instruction()
                    inst.set_name_constraint('ILLEGAL')
                    inst.solve()
                    victim_record[key] = inst
                else:
                    victim_record[key] = Instruction(' '.join(value_seq))
            elif key == 'encode_type':
                encode_list = []
                for value in value_seq:
                    encode_list.append(eval(value))
                victim_record[key] = encode_list
            else:
                victim_record[key] = eval(value_seq[0])
            self.eat_field()
        return victim_record

    def parse_iter(self):
        record = {}
        
        header = self.parse_header()
        if header is None:
            return None
        record['head'] = header

        result = self.parse_result()
        if result is None:
            return None
        record['result'] = result

        record['train'] = []
        while True:
            train = self.parse_train()
            if train is None:
                break
            else:
                record['train'].append(train)

        victim = self.parse_victim()
        if victim is None:
            return None
        record['victim'] = victim

        return record       

    def load_stage_record(self):
        self.token_generate()

        self.record = []
        while True:
            iter_result = self.parse_iter()
            if iter_result is None:
                break
            self.record.append(iter_result)
    
    def trigger_analysis(self):
        self.trigger_result = {}
        for record in self.record:
            trigger_type = record['victim']['trigger_type']
            if (not trigger_type in self.trigger_result):
                self.trigger_result[trigger_type] = {}
                self.trigger_result[trigger_type]['summary'] = 0
                self.trigger_result[trigger_type]['success'] = 0
                self.trigger_result[trigger_type]['failure'] = 0
                self.trigger_result[trigger_type]['train'] = {}
            trigger_result = self.trigger_result[trigger_type]
            trigger_result['summary'] += 1
            if record['result']['result'] == FuzzResult.SUCCESS:
                trigger_result['success'] += 1
                if len(record['train']) != 0:
                    train_type = record['train'][0].get('train_type', TrainType.NONE)
                    trigger_result['train'][train_type] = trigger_result['train'].get(train_type, 0) + 1
                else:
                    trigger_result['train'][TrainType.NONE] = trigger_result['train'].get(TrainType.NONE, 0) + 1
            else:
                trigger_result['failure'] += 1

        with open(self.output_file, "wt") as file:
            file.write('|trigger_type|summary|failure|success|failure_rate|success_rate|\n')
            file.write('|:----------:|:-----:|:-----:|:-----:|:----------:|:----------:|\n')
            for trigger_type, trigger_record in self.trigger_result.items():
                summary = trigger_record['summary']
                failure = trigger_record['failure']
                success = trigger_record['success']
                failure_rate = failure/summary
                success_rate = success/summary
                file.write(f'|{trigger_type}|{summary}|{failure}|{success}|{failure_rate:.2%}|{success_rate:.2%}|\n')
            file.write('\n')

            file.write('|trigger_type|train_type|summary|rate|\n')
            file.write('|:----------:|:--------:|:-----:|:--:|\n')
            for trigger_type, trigger_record in self.trigger_result.items():
                for train_type, summary in trigger_record['train'].items():
                    rate = summary/trigger_record['success']
                    file.write(f'|{trigger_type}|{train_type}|{summary}|{rate:.2%}|\n')
            file.write('\n')            

if __name__ == "__main__":
    parse = argparse.ArgumentParser(description="the analysis script for stage record of fuzz")
    parse.add_argument("--input", "-I", dest="input", required=True, help="stage record file")
    parse.add_argument("--output", "-O", dest="output", default="build", help="record analysis result")
    parse.add_argument("--mode", dest="mode", default="trigger_kind", help="the analysis target")
    args = parse.parse_args()

    record_analysis = RecordAnalysis(args.input, args.output)
    record_analysis.load_stage_record()
    match(args.mode):
        case 'trigger':
            record_analysis.trigger_analysis()
        case _:
            raise Exception(f"the mode {args.mode} is not supported!!!")



    