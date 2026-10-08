import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ExecutionProtocolAnchorContractTests(unittest.TestCase):
    """C01/R06 契约:进度锚点、可证伪完成声明、磁盘锚点续接随协议/模板/角色文件发布。

    仿 test_document_contract 的关键词契约模式:三个条款的关键短语必须出现在
    执行协议与对应模板/角色文件中;措辞漂移即测试失败,防止条款在单源文件丢失。
    """

    def setUp(self):
        self.protocol = (ROOT / 'skills/longdev/references/execution-protocol.md').read_text('utf-8')
        self.stage_template = (ROOT / 'skills/longdev/references/stage-template.md').read_text('utf-8')
        self.plan_template = (ROOT / 'skills/longdev/references/plan-template.md').read_text('utf-8')
        self.implementer = (ROOT / 'agents/longdev-implementer.md').read_text('utf-8')

    def test_progress_anchor_rule_present(self):
        # (a) 每完成一个可验证子项立即追加进度行;探索结论同样落盘,不以纯探索为由零落盘。
        for phrase in ('每完成一个可验证子项',
                       '追加一条进度行',
                       '不以结束前一次性补写替代',
                       '纯探索无产物'):
            self.assertIn(phrase, self.protocol)

    def test_falsifiable_completion_declaration_present(self):
        # (b) 完成声明必须可证伪:附子项到证据路径的清单,缺锚点无效。
        for phrase in ('子项到证据路径的清单',
                       '完成声明无效',
                       '不得据此进入检查'):
            self.assertIn(phrase, self.protocol)

    def test_disk_anchor_resume_rule_present(self):
        # (c) 续派/恢复提示必须包含磁盘现状+已落盘锚点+唯一下一步。
        for phrase in ('磁盘现状',
                       '已落盘锚点',
                       '唯一下一步',
                       '不作续接依据'):
            self.assertIn(phrase, self.protocol)

    def test_silent_hang_liveness_rule_present(self):
        # (d) 静默挂起判定:锚点停滞超复核点且无完成通知→状态检查→确认后从锚点续接或重派。
        for phrase in ('复核点判定子代理死活以磁盘进度锚点为准',
                       '疑似静默挂起',
                       '不以长时间零写入默认为仍在执行',
                       '不无限顺延复核点'):
            self.assertIn(phrase, self.protocol)

    def test_templates_carry_matching_fields(self):
        # 模板字段与协议条款一致:阶段记录承载进度锚点与完成声明清单,交接含磁盘锚点。
        self.assertIn('进度锚点', self.stage_template)
        self.assertIn('不以结束时一次性补写替代', self.stage_template)
        self.assertIn('完成声明清单', self.stage_template)
        self.assertIn('磁盘现状', self.plan_template)
        self.assertIn('已落盘锚点', self.plan_template)
        self.assertIn('唯一下一步', self.plan_template)

    def test_implementer_role_matches_protocol_clauses(self):
        # 角色文件与协议条款一致且详情引协议,不复制第二套规则正文。
        self.assertIn('execution-protocol.md', self.implementer)
        self.assertIn('每完成一个可验证子项立即追加一条进度行', self.implementer)
        self.assertIn('完成声明附子项→证据路径清单', self.implementer)
        self.assertIn('磁盘现状和已落盘锚点', self.implementer)


if __name__ == '__main__':
    unittest.main()
