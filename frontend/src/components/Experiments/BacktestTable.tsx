import React, { FC } from "react";
import { BacktestType } from "../../types/experiment-type";
import type { ProColumns } from "@ant-design/pro-components";
import { ProTable } from "@ant-design/pro-components";
import { Tag } from "antd";

const columns: ProColumns<BacktestType>[] = [
  {
    title: "Name",
    dataIndex: "backtest_name",
    align: "left",
  },
  {
    title: "Date Created",
    width: 120,
    dataIndex: "time_created",
    align: "left",
  },
  {
    title: "KPIs",
    width: 120,
    dataIndex: "kpis",
    render: (_, record) => (
      <div>
        {record.kpis.map((kpi) => (
          <Tag color={"default"}>{kpi}</Tag>
        ))}
      </div>
    ),
  },
  {
    title: "Status",
    width: 120,
    dataIndex: "status",
  },
];

interface Props {
  backtests: BacktestType[];
}

const BacktestTable: FC<Props> = ({ backtests }) => {
  return (
    <div>
      <ProTable
        columns={columns}
        dataSource={backtests}
        search={{ filterType: "light" }}
        options={false}
        toolBarRender={() => []}
      />
    </div>
  );
};

export default BacktestTable;
