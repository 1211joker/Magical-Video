"""使用资料库中真实的前三讲验证前 8 个候选是否覆盖标注的字幕时间段。"""

import argparse
from dataclasses import dataclass

from services.study_embeddings import LocalEmbeddings, data_directory, model_directory
from services.study_search import follow_up_query, retrieve
from storage.study_db import StudyDatabase

VIDEO_IDS = {1: "aircAruvnKk", 2: "IHZwWFHWa-w", 3: "Ilg3gGewQ5U"}


@dataclass(frozen=True)
class Case:
    kind: str
    question: str
    # 每个知识点标出讲次和内容所在的秒数。跨视频题须覆盖每个知识点。
    expected: tuple[tuple[int, int, int], ...]
    recent: tuple[str, str] = ("", "")


CASES = [
    Case("单视频", "How many input neurons represent the 28 by 28 pixel image, and what does each neuron represent?", ((1, 184, 218),)),
    Case("单视频", "What does the sigmoid do to a weighted sum before the neuron produces an activation?", ((1, 612, 651),)),
    Case("单视频", "How do squared differences between actual and target activations define the cost of one example?", ((2, 224, 247),)),
    Case("单视频", "Why can following the slope end up at a local minimum that is not the smallest possible point?", ((2, 363, 403),)),
    Case("单视频", "What is a mini-batch and how are those batches used to compute a step?", ((3, 580, 620),)),
    Case("单视频", "What are the three avenues to influence an output activation through a weight, bias or previous activation?", ((3, 294, 335),)),
    Case("跨视频", "Compare the representation of each digit by an output neuron in lecture 1 and the squared output activation differences in lecture 2.", ((1, 222, 250), (2, 224, 247))),
    Case("跨视频", "What is the difference between the average cost over all training examples in lecture 2 and steps computed from mini-batches in lecture 3?", ((2, 253, 270), (3, 580, 620))),
    Case("跨视频", "How is the direction of steepest ascent introduced in gradient descent, and what is the negative gradient backpropagation helps compute?", ((2, 446, 480), (3, 85, 117))),
    Case("跨视频", "How does adding a bias before sigmoid in lecture 1 relate to the three avenues for changing an activation in lecture 3?", ((1, 651, 699), (3, 294, 335))),
    Case("跨视频", "Connect the squared differences of expected output in lecture 2 to the example in lecture 3 where the output for digit 2 should be higher.", ((2, 224, 247), (3, 225, 268))),
    Case("跨视频", "How is the average cost over all examples related to averaging desired nudges to the weights and biases from individual examples?", ((2, 253, 270), (3, 520, 549))),
    Case("跨视频", "In lecture 1 how is a weighted sum formed from previous activations, and in lecture 3 why does a larger preceding activation make a weight change more influential?", ((1, 551, 568), (3, 312, 351))),
    Case("跨视频", "Why can the cost function have a local minimum in lecture 2, while stochastic gradient descent in lecture 3 takes noisier steps based on batches?", ((2, 363, 403), (3, 602, 643))),
    Case("中英及同义", "为什么 28×28 图像的每个像素要对应一个输入神经元，输入层一共有多少个？", ((1, 184, 218),)),
    Case("中英及同义", "一元函数的斜率如何决定 gradient descent 每一步的方向和步长？", ((2, 343, 369),)),
    Case("中英及同义", "随机梯度下降怎样使用 mini-batch，为什么不用每次遍历全量训练样本？", ((3, 580, 643),)),
    Case("中英及同义", "隐藏层是怎么从边缘和圆圈等局部结构组合成数字的？", ((1, 398, 465),)),
    Case("中英及同义", "sigmoid 如何把任意大小的加权和压缩到 0 和 1 之间？", ((1, 612, 651),)),
    Case("中英及同义", "反向传播里，为什么除了权重和偏置，还要计算上一层 activation 希望发生什么变化？", ((3, 294, 357),)),
    Case("追问", "第二点能再展开讲讲吗", ((2, 253, 270),),
         ("讲解如何定义训练网络的误差。", "1. 对单个样本计算代价。\n2. 取所有训练样本的平均代价（average cost over all training examples）。")),
    Case("追问", "第一点能说明一下吗", ((1, 184, 218),),
         ("解析手写数字网络的输入和输出。", "1. 输入层为 28×28 图像的各像素分配神经元（784 input neurons）。\n2. 输出层预测类别。")),
    Case("追问", "第三点具体指什么", ((3, 580, 643),),
         ("反向传播和训练如何配合？", "1. 处理单个样本。\n2. 反向计算更新。\n3. 小批量（mini-batch）让随机梯度下降每步只看一部分样本。")),
    Case("追问", "它为什么还可能卡住？", ((2, 363, 403),),
         ("为什么 gradient descent 会陷入局部最小值（local minimum）？", "梯度下降每一步沿当前的坡度改变参数。")),
]


def measure(connection, course_id, encoder):
    videos = {row["external_id"]: row["id"] for row in connection.execute(
        "SELECT v.id, v.external_id FROM membership m JOIN videos v ON v.id=m.video_id "
        "WHERE m.course_id=? AND v.platform='youtube'", (course_id,),
    )}
    missing = set(VIDEO_IDS.values()) - videos.keys()
    if missing:
        raise ValueError(f"课程尚缺少验收所需的公开视频 {sorted(missing)}")
    video_ids = {item: videos[value] for item, value in VIDEO_IDS.items()}
    correct = 0
    for index, case in enumerate(CASES, 1):
        context = [{"question": case.recent[0], "answer": case.recent[1]}] if case.recent[0] else []
        query = follow_up_query(case.question, context)
        vector = encoder.vectors([query], query=True)
        if vector is None:
            raise RuntimeError("本地语义模型未就绪")
        scope = "video" if case.kind == "单视频" else "course"
        scope_id = video_ids[case.expected[0][0]] if scope == "video" else course_id
        results, _ = retrieve(connection, scope, scope_id, query, vector[0])
        matched = [
            any(hit["video_id"] == video_ids[lecture] and hit["start_time"] < end and hit["end_time"] > start
                for hit in results)
            for lecture, start, end in case.expected
        ]
        correct += all(matched)
        keys = {value: lecture for lecture, value in video_ids.items()}
        positions = " ".join(f'{keys.get(hit["video_id"], "?")}@{int(hit["start_time"])}-{int(hit["end_time"])}'
                             for hit in results)
        print(f'{index:02d} {case.kind} {"PASS" if all(matched) else "MISS"} {matched} {positions}')
    print(f"Top-8 full evidence: {correct}/{len(CASES)}")
    return correct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course", required=True, help="验收课程 ID，可在课程页地址中查看")
    args = parser.parse_args()
    directory = data_directory()
    database = StudyDatabase(directory / "library.sqlite3")
    if not database.path.is_file():
        raise SystemExit("请先使用应用分析并保存三条验收视频")
    encoder = LocalEmbeddings(model_directory(directory))
    if not encoder.load():
        raise SystemExit("请先准备本地 E5 模型")
    with database.transaction() as connection:
        if connection.execute("SELECT 1 FROM search_docs WHERE embedding IS NULL LIMIT 1").fetchone():
            raise SystemExit("请先等应用完成语义索引")
        passed = measure(connection, args.course, encoder)
    raise SystemExit(0 if passed >= 21 else 1)


if __name__ == "__main__":
    main()
