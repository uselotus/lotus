import React, { FC } from "react";
import type { ProColumns } from "@ant-design/pro-components";
import { ProTable } from "@ant-design/pro-components";
import { Tag } from "antd";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import dayjs from "dayjs";
import { BacktestType } from "../../types/experiment-type";
import { components } from "../../gen-types";

const columns: ProColumns<BacktestType>[] = [
  {
    width: 10,
  },
  {
    title: "Name",
    dataIndex: "analysis_name",
    align: "left",
    width: 120,
  },
  {
    title: "Date Created",
    width: 150,
    dataIndex: "time_created",
    align: "left",
    sorter: (a, b) => a.time_created.localeCompare(b.time_created),
    render: (text) => dayjs(text?.toString()).format("YYYY-MM-DD"),
  },
  {
    title: "KPIs",
    width: 200,
    dataIndex: "kpis",
    render: (_, record) => (
      <div>
        {record.kpis.map((kpi) => (
          <Tag color="default">{kpi}</Tag>
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
  experiments: components["schemas"]["AnalysisSummary"][];
}

const ExperimentsTable: FC<Props> = ({ experiments }) => {
  const navigate = useNavigate();
  const navigateToExperiment = (
    row: components["schemas"]["AnalysisSummary"]
  ) => {
    navigate(`/experiment/${row.analysis_id}`);
  };
  return (
    <div className="border-2 border-solid rounded border-[#EAEAEB]">
      <ProTable
        columns={columns}
        dataSource={experiments}
        options={false}
        toolBarRender={false}
        search={false}
        onRow={(record, rowIndex) => ({
          onClick: (event) => {
            if (record.status === "completed") {
              navigateToExperiment(record);
            } else {
              toast("Experiment is still running");
            }
          }, // click row
        })}
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

export default ExperimentsTable;
