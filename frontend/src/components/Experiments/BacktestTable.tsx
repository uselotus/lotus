import React, { FC } from "react";
import { BacktestType } from "../../types/experiment-type";
import type { ProColumns } from "@ant-design/pro-components";
import { ProTable } from "@ant-design/pro-components";
import { Tag } from "antd";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import dayjs from "dayjs";

const columns: ProColumns<BacktestType>[] = [
  {
    title: "Name",
    dataIndex: "backtest_name",
    align: "left",
  },
  // {
  //   title: "Creator",
  //   dataIndex: "creator",
  //   align: "left",
  //   width: 150,
  // },
  {
    title: "Date Created",
    width: 150,
    dataIndex: "time_created",
    align: "left",
    sorter: (a, b) => a.time_created.localeCompare(b.time_created),
    render: (text) => {
      return dayjs(text?.toString()).format("YYYY-MM-DD");
    },
  },
  {
    title: "KPIs",
    width: 200,
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
    sorter: (a, b) => a.status.localeCompare(b.status),
  },
];

interface Props {
  backtests: BacktestType[];
}

const BacktestTable: FC<Props> = ({ backtests }) => {
  const navigate = useNavigate();
  const navigateToExperiment = (row: BacktestType) => {
    navigate(`/experiment/${row.backtest_id}`);
  };
  return (
    <div>
      <ProTable
        columns={columns}
        dataSource={backtests}
        options={false}
        toolBarRender={false}
        search={false}
        onRow={(record, rowIndex) => {
          return {
            onClick: (event) => {
              if (record.status === "completed") {
                navigateToExperiment(record);
              } else {
                toast("Experiment is still running");
              }
            }, // click row
          };
        }}
        pagination={{
          showTotal: (total, range) => (
            <div>{`${range[0]}-${range[1]} of ${total} total items`}</div>
          ),
          pageSize: 10,
        }}
      />
    </div>
  );
};

export default BacktestTable;
