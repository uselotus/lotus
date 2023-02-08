import React, { useState } from "react";
import { Modal, Select } from "antd";
import { UseQueryResult, useQuery } from "react-query";
import { Customer } from "../../api/api";
import { CustomerSummary } from "../../types/customer-type";

const { Option } = Select;

function TargetCustomerForm({
  onCancel,
  onAddTargetCustomer,
  visible,
}: {
  visible: boolean;
  onCancel: () => void;
  onAddTargetCustomer: (target_customer_id: string) => void;
}) {
  const [targetCustomer, setTargetCustomer] = useState<string>(""); // id of the target customer

  const { data: customers }: UseQueryResult<CustomerSummary[]> = useQuery<
    CustomerSummary[]
  >(["customer_list"], () => Customer.getCustomers().then((res) => res));

  return (
    <Modal
      visible={visible}
      title="Choose Target Customer For Plan"
      okText="Confirm and Create Plan"
      okType="default"
      okButtonProps={{
        type: "primary",
      }}
      onCancel={onCancel}
      onOk={() => {
        onAddTargetCustomer(targetCustomer);
      }}
    >
      <div className="grid grid-row-3">
        <div className="flex flex-col">
          <Select
            placeholder="Choose Target Customer"
            showSearch
            onChange={(value) => {
              setTargetCustomer(value);
            }} // id of the target customer)}
          >
            {customers?.map((customer) => (
              <Option key={customer.customer_id} value={customer.customer_id}>
                {customer.customer_name}
              </Option>
            ))}
          </Select>
        </div>
      </div>
    </Modal>
  );
}

export default TargetCustomerForm;
