import React, { useState } from "react";
import { Modal, Select } from "antd";
import { UseQueryResult, useQuery } from "react-query";
import { Customer } from "../../api/api";
import { CustomerPlus } from "../../types/customer-type";

const { Option } = Select;

const TargetCustomerForm = (props: {
  visible: boolean;
  onCancel: () => void;
  onAddTargetCustomer: (target_customer_id: string) => void;
}) => {
  const [targetCustomer, setTargetCustomer] = useState<string>(""); //id of the target customer

  const { data: customers, isLoading }: UseQueryResult<CustomerPlus[]> =
    useQuery<CustomerPlus[]>(["customer_list"], () =>
      Customer.getCustomers().then((res) => {
        return res;
      })
    );

  return (
    <Modal
      visible={props.visible}
      title={"Choose Target Customer For Plan"}
      okText="Confirm and Create Plan"
      okType="default"
      okButtonProps={{
        type: "primary",
      }}
      onCancel={props.onCancel}
      onOk={() => {
        props.onAddTargetCustomer(targetCustomer);
      }}
    >
      <div className="grid grid-row-3">
        <div className="flex flex-col">
          <Select
            placeholder="Choose Target Customer"
            showSearch
            onChange={(value) => {
              setTargetCustomer(value);
            }} //id of the target customer)}
          >
            {customers?.map((customer) => (
              <Option value={customer.customer_id}>
                {customer.customer_name}
              </Option>
            ))}
          </Select>
        </div>
      </div>
    </Modal>
  );
};

export default TargetCustomerForm;
