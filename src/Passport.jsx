import React from 'react';
import { Network } from 'vis-network';
import Modal from 'react-modal';

const Passport = ({ graphData }) => {
  const [modalIsOpen, setModalIsOpen] = React.useState(false);
  const [nodeDetails, setNodeDetails] = React.useState({});

  React.useEffect(() => {
    const container = document.getElementById('graph');
    const options = {};
    const network = new Network(container, graphData, options);
    network.on('click', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        fetch(`/graph/node/${nodeId}`)
          .then(res => res.json())
          .then(data => {
            setNodeDetails(data);
            setModalIsOpen(true);
          });
      }
    });
  }, [graphData]);

  return (
    <div id="graph" style={{ height: '500px' }}></div>
    <Modal isOpen={modalIsOpen} onRequestClose={() => setModalIsOpen(false)}>
      <h2>Node Details</h2>
      <pre>{JSON.stringify(nodeDetails, null, 2)}</pre>
    </Modal>
  );
};

export default Passport;
