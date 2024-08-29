import json

from dbgpt._private.config import Config
from dbgpt.app.scene import AppScenePromptTemplateAdapter, ChatScene
from dbgpt.app.scene.chat_db.auto_execute.out_parser import DbChatOutputParser
from dbgpt.core import (
    ChatPromptTemplate,
    HumanPromptTemplate,
    MessagesPlaceholder,
    SystemPromptTemplate,
)

CFG = Config()


_PROMPT_SCENE_DEFINE_EN = "You are a database expert. "
_PROMPT_SCENE_DEFINE_ZH = "你是一个数据库专家. "

_DEFAULT_TEMPLATE_EN = """
<|begin_of_text|><|start_header_id|>user<|end_header_id|>

Generate a SQL query to answer this question: `{user_input}`
{response}

DDL statements:
CREATE TABLE IF NOT EXISTS "workload_runs" (
	"workload_run_id"	BIGINT NOT NULL, -- Primary Key of the table
	"platform"	TEXT NOT NULL, -- Also known as Microarchitecture. Always use ILIKE operator for this column
	"workload_name"	TEXT NOT NULL, -- Always Use ILIKE operator, known as workload name
	"workload_category"	TEXT NOT NULL, -- Also known as Domain
    "workload_subcategory"	TEXT,
	"primary_kpi_name"	TEXT NOT NULL, -- Also known as kpi_metric
	"primary_kpi_value"	FLOAT, -- Also known as Value
	PRIMARY KEY("workload_run_id")
);

CREATE TABLE IF NOT EXISTS "software_configuration" (
	"workload_run_id"	BIGINT NOT NULL, -- Foreign key which references to table workload runs
	"software_config_name"	TEXT NOT NULL,  -- Key to be considered. also known as Software configuration or Ingredient
	"software_config_value"	TEXT, -- Value of software_config_name.
	PRIMARY KEY("workload_run_id","software_config_name"),
	FOREIGN KEY("workload_run_id") REFERENCES "workload_runs"("workload_run_id")
);

CREATE TABLE IF NOT EXISTS "edp" (
	"workload_run_id"	BIGINT NOT NULL, -- Foreign key which references to table workload runs
	"metric_name"	TEXT NOT NULL, -- Also known as emon metric name or edp metric or edp event name. Always use ILIKE operator for this column. Some metric names like metric_package power are also called as package power.
	"metric_value"	FLOAT, -- value to be considered
	PRIMARY KEY("workload_run_id","metric_name"),
	FOREIGN KEY("workload_run_id") REFERENCES "workload_runs"("workload_run_id")
) COMMNENT ON TABLE "Also known as Emon Events";

CREATE TABLE IF NOT EXISTS "tuning_parameters" (
	"workload_run_id"	BIGINT NOT NULL, -- Foreign key which references to table workload runs
	"tuning_parameter_name"	TEXT NOT NULL, -- Key to be considered. also known as Tuning parameter
	"tuning_parameter_value"	TEXT,  -- Value of tuning_parameter_name.
	PRIMARY KEY("workload_run_id","tuning_parameter_name"),
	FOREIGN KEY("workload_run_id") REFERENCES "workload_runs"("workload_run_id")
);

CREATE TABLE IF NOT EXISTS "instructions" (
	"workload_name"	TEXT NOT NULL,  -- Also known as workload name
	"platform"	TEXT NOT NULL, -- Also known as microarchitecture
	"workload_category"	TEXT, -- Also known as Domain
	"release_version"	TEXT NOT NULL, -- Release version of the particular workload
	"instruction_name"	TEXT NOT NULL, -- Also known as instruction or instruction name that is captured during workload run or execution
	"instruction_frequency"	FLOAT NOT NULL, -- Total count of instruction_name that was used in the worklaod run or execution
	PRIMARY KEY("workload_name","platform","release_version","instruction_name")
);

CREATE TABLE IF NOT EXISTS "platform_info" (
	"workload_run_id"	BIGINT NOT NULL, -- Foreign key which references to table workload runs
	"cpus"	INTEGER NOT NULL, -- Total number of CPU's
	"core_count"	INTEGER NOT NULL, -- Total number of cores in the CPU
	"core_frequency_ghz"	FLOAT NOT NULL, -- Frequency in Ghz for the corresponding CPU
	"epb_bios"	TEXT, -- also known as Bios version
	"hyperthreading"	BOOL, -- Hyperthreading value. Hyperthreading is enabled if value is true and disabled if value is false
	"l2c_size_mb"	FLOAT, -- also known as level 2 cache or secondary cache value
	"llc_size_mb"	FLOAT, -- known as llc size or last level cache value
	"power"	TEXT,
	"snc_mode"	INTEGER, -- Sub numa cluster mode
	"sockets"	INTEGER, -- Number of sockets 
	"uncore_frequency"	TEXT,
	"memory_speed_mt_s"	INTEGER, -- Memory speed in Milliontransfer per second.
	"workload_name"	TEXT,  -- Known as workload name
	"workload_category"	TEXT, -- Also known as Domain
	"platform"	TEXT, -- Also known as microarchitecture
	PRIMARY KEY("workload_run_id"),
	FOREIGN KEY("workload_run_id") REFERENCES "workload_runs"("workload_run_id")
);
<|eot_id|><|start_header_id|>assistant<|end_header_id|>

The following SQL query best answers the question `{user_input}`:
```sql
"""

_DEFAULT_TEMPLATE_ZH = """
请根据用户选择的数据库和该库的部分可用表结构定义来回答用户问题.
数据库名:
    {db_name}
表结构定义:
    {table_info}

约束:
    1. 请根据用户问题理解用户意图，使用给出表结构定义创建一个语法正确的 {dialect} sql，如果不需要sql，则直接回答用户问题。
    2. 除非用户在问题中指定了他希望获得的具体数据行数，否则始终将查询限制为最多 {top_k} 个结果。
    3. 只能使用表结构信息中提供的表来生成 sql，如果无法根据提供的表结构中生成 sql ，请说：“提供的表结构信息不足以生成 sql 查询。” 禁止随意捏造信息。
    4. 请注意生成SQL时不要弄错表和列的关系
    5. 请检查SQL的正确性，并保证正确的情况下优化查询性能
    6.请从如下给出的展示方式种选择最优的一种用以进行数据渲染，将类型名称放入返回要求格式的name参数值种，如果找不到最合适的则使用'Table'作为展示方式，可用数据展示方式如下: {display_type}
用户问题:
    {user_input}
请一步步思考并按照以下JSON格式回复：
      {response}
确保返回正确的json并且可以被Python json.loads方法解析.

"""

_DEFAULT_TEMPLATE = (
    _DEFAULT_TEMPLATE_EN if CFG.LANGUAGE == "en" else _DEFAULT_TEMPLATE_ZH
)

PROMPT_SCENE_DEFINE = (
    _PROMPT_SCENE_DEFINE_EN if CFG.LANGUAGE == "en" else _PROMPT_SCENE_DEFINE_ZH
)

RESPONSE_FORMAT_SIMPLE = {
    "thoughts": "thoughts summary to say to user",
    "sql": "SQL Query to run",
    "display_type": "Data display method",
}


PROMPT_NEED_STREAM_OUT = False

# Temperature is a configuration hyperparameter that controls the randomness of language model output.
# A high temperature produces more unpredictable and creative results, while a low temperature produces more common and conservative output.
# For example, if you adjust the temperature to 0.5, the model will usually generate text that is more predictable and less creative than if you set the temperature to 1.0.
PROMPT_TEMPERATURE = 0.5

prompt = ChatPromptTemplate(
    messages=[
        SystemPromptTemplate.from_template(
            _DEFAULT_TEMPLATE,
            response_format=json.dumps(
                RESPONSE_FORMAT_SIMPLE, ensure_ascii=False, indent=4
            ),
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanPromptTemplate.from_template("{user_input}"),
    ]
)

prompt_adapter = AppScenePromptTemplateAdapter(
    prompt=prompt,
    template_scene=ChatScene.ChatWithDbExecute.value(),
    stream_out=PROMPT_NEED_STREAM_OUT,
    output_parser=DbChatOutputParser(is_stream_out=PROMPT_NEED_STREAM_OUT),
    temperature=PROMPT_TEMPERATURE,
    need_historical_messages=False,
)
CFG.prompt_template_registry.register(prompt_adapter, is_default=True)
